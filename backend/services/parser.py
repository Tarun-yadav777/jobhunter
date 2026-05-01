import hashlib
import io
import json
import logging
import re

import ftfy
import pdfplumber
from ollama import AsyncClient

from backend.config import settings
from backend.models.schemas import CvExtracted, JdExtracted

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

CV_EXTRACTION_PROMPT = """
You are parsing a CV. Extract the following fields and return ONLY valid JSON.

CV text:
{cv_text}

Return this exact JSON structure:
{{
  "full_name": "string",
  "email": "string or null",
  "location": "string or null",
  "summary": "string or null",
  "total_years_experience": number or null,
  "experiences": [
    {{
      "title": "string",
      "company": "string",
      "start_date": "string",
      "end_date": "string or Present",
      "description": "string",
      "skills_used": ["string"]
    }}
  ],
  "skills": {{
    "technical": ["string"],
    "tools": ["string"],
    "soft": ["string"]
  }},
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "year": "string or null"
    }}
  ],
  "certifications": ["string"],
  "languages": ["string"]
}}

Rules:
- Return ONLY the JSON object, no explanation
- Keep descriptions verbatim from the CV — do not paraphrase
- Do not invent or infer information not present
- If a field is missing use null or empty array
"""

JD_EXTRACTION_PROMPT = """
You are parsing a job description. Extract structured information and return ONLY valid JSON.

Job description:
{jd_text}

Return exactly this JSON structure:
{{
  "title": "string",
  "company": "string",
  "location": "string or null",
  "remote_type": "remote" | "hybrid" | "onsite" | "unknown",
  "salary_min": number or null,
  "salary_max": number or null,
  "salary_currency": "EUR" | "USD" | "GBP" | null,
  "seniority": "entry" | "mid" | "senior" | "lead" | "staff" | "unknown",
  "skills_required": ["string"],
  "skills_preferred": ["string"],
  "ats_keywords": ["exact terms and acronyms the ATS will scan for — include both full form and abbreviation"],
  "posted_date": "YYYY-MM-DD or null",
  "description_summary": "2-3 sentence plain English summary"
}}

Rules:
- Return ONLY the JSON, no explanation, no markdown fences
- skills_required = explicitly stated must-haves
- skills_preferred = nice-to-haves or bonus skills
- ats_keywords = exact strings as they appear in JD including acronyms both ways e.g. "NLP" and "Natural Language Processing"
- Never invent information not in the text
"""

# ── PDF helpers ───────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pdfplumber."""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def clean_cv_text(raw_text: str) -> str:
    """Fix encoding artefacts and normalise whitespace."""
    text = ftfy.fix_text(raw_text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_jd_text(raw_text: str) -> str:
    """Normalise a pasted job description — fix encoding, collapse excess whitespace."""
    text = ftfy.fix_text(raw_text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_jd_text(text: str) -> tuple[bool, str]:
    """Return (ok, error_code). Min 200 chars, max 50 000 chars."""
    if len(text) < 200:
        return False, "too_short"
    if len(text) > 50_000:
        return False, "too_long"
    return True, ""


def compute_hash(data: bytes) -> str:
    """SHA-256 hex digest of arbitrary bytes."""
    return hashlib.sha256(data).hexdigest()


# ── Ollama CV extraction ──────────────────────────────────────────────────────

async def extract_cv_with_claude(raw_text: str) -> dict:
    """Call Ollama to parse CV text into structured JSON. Retries once on failure."""
    client = AsyncClient(host=settings.ollama_host)
    prompt = CV_EXTRACTION_PROMPT.format(cv_text=raw_text)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = await client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format=CvExtracted.model_json_schema(),
            )
            return json.loads(response['message']['content'])
        except json.JSONDecodeError as exc:
            logger.warning("CV JSON parse error (attempt %d): %s", attempt + 1, exc)
            last_error = exc
        except Exception as exc:
            logger.warning("Ollama error (attempt %d): %s", attempt + 1, exc)
            last_error = exc

    raise RuntimeError(f"CV extraction failed after 2 attempts: {last_error}") from last_error


# ── Ollama JD extraction ──────────────────────────────────────────────────────

async def extract_jd_with_claude(clean_text: str) -> dict:
    """Call Ollama to parse a job description into structured JSON. Retries once."""
    client = AsyncClient(host=settings.ollama_host)
    prompt = JD_EXTRACTION_PROMPT.format(jd_text=clean_text)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = await client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format=JdExtracted.model_json_schema(),
            )
            return json.loads(response['message']['content'])
        except json.JSONDecodeError as exc:
            logger.warning("JD JSON parse error (attempt %d): %s", attempt + 1, exc)
            last_error = exc
        except Exception as exc:
            logger.warning("Ollama error (attempt %d): %s", attempt + 1, exc)
            last_error = exc

    raise RuntimeError(f"JD extraction failed after 2 attempts: {last_error}") from last_error
