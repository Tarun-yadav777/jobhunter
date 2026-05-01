import json
import logging

from ollama import AsyncClient

from backend.config import settings
from backend.models.schemas import GapAnalysis, ResumeJson

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

GAP_ANALYSIS_PROMPT = """
You are a senior technical recruiter and career coach analysing a candidate's fit for a role.

JOB REQUIREMENTS:
Title: {title}
Company: {company}
Seniority: {seniority}
Required skills: {skills_required}
Preferred skills: {skills_preferred}
Job description summary: {description_summary}

CANDIDATE PROFILE — most relevant experience sections:
{cv_chunks}

Candidate preferences and context:
- Target roles: {target_roles}
- Skills they want to grow into: {skills_to_grow}
- Tone preference: {tone_preference}
- Extra context: {extra_context}

Analyse the fit and return ONLY this JSON:
{{
  "match_score": 0-100,
  "matched_skills": ["skills clearly present in candidate profile"],
  "soft_gaps": ["skills missing but candidate has adjacent experience to reframe"],
  "hard_gaps": ["skills genuinely missing with no adjacent experience"],
  "strengths_to_emphasise": ["2-4 specific strengths that fit this role"],
  "reframe_opportunities": [
    {{
      "gap": "skill or experience gap",
      "reframe": "how to honestly present adjacent experience"
    }}
  ],
  "strategy": "2-3 sentence plain English strategy for this application",
  "red_flags": ["any serious mismatches worth flagging"]
}}

Rules:
- Be honest — do not invent matches that are not there
- Soft gaps are bridgeable through honest reframing of real experience
- Hard gaps must be flagged clearly, never hidden
- Match score reflects genuine fit not keyword overlap
"""

RESUME_TAILORING_PROMPT = """
You are an expert CV writer tailoring a resume for a specific role.

TARGET ROLE: {title} at {company}
SENIORITY: {seniority}

GAP ANALYSIS STRATEGY: {strategy}
STRENGTHS TO EMPHASISE: {strengths_to_emphasise}
REFRAMING GUIDANCE: {reframe_opportunities}

ATS OPTIMISATION — CRITICAL:
These exact keywords must appear naturally in the resume:
{ats_keywords}
Rules for ATS keywords:
- Use exact spelling and capitalisation from the list
- Include both acronym and full form at least once e.g. "Natural Language Processing (NLP)"
- Never list keywords in isolation — weave them into real bullet points
- Place high-frequency JD terms in the summary and first bullet of most relevant role
- Do not invent experience to accommodate a keyword

CANDIDATE RELEVANT EXPERIENCE (RAG retrieved):
{cv_chunks}

CANDIDATE FULL PARSED CV:
{cv_parsed_json}

Produce a tailored resume and return ONLY this JSON:
{{
  "full_name": "string",
  "contact": "email | location | any other contact info from CV",
  "summary": "3-4 sentence professional summary tailored to this role",
  "experiences": [
    {{
      "title": "string",
      "company": "string",
      "dates": "string",
      "bullets": ["achievement bullet — quantified where data exists in original CV"]
    }}
  ],
  "skills": {{
    "technical": ["string"],
    "tools": ["string"]
  }},
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "year": "string or null"
    }}
  ]
}}

Critical rules:
- Only use experience present in the candidate's CV — never invent
- Never invent — never invent — this rule cannot be broken
- Reorder bullets to lead with most relevant achievements for this role
- Quantify achievements only where the data exists in the original CV
- Keep all dates and company names exactly as in the original CV
- Tone: {tone_preference}
"""

COVER_LETTER_PROMPT = """
You are writing a cover letter for a job application.

ROLE: {title} at {company}
LOCATION: {location}

GAP ANALYSIS:
- Match score: {match_score}/100
- Key strengths for this role: {strengths_to_emphasise}
- Strategy: {strategy}

CANDIDATE CONTEXT: {extra_context}

RELEVANT EXPERIENCE:
{cv_chunks}

PREFERENCES:
- Tone: {tone_preference}
- Seniority target: {seniority_target}
- Length: {cover_letter_length}

Write a cover letter in plain text with this structure:
1. Opening — specific hook about this company or role, not generic
2. Why this role — connect their needs to candidate strengths
3. Specific evidence — 1-2 concrete examples from their experience
4. Growth alignment — connect role to candidate growth goals if relevant
5. Close — confident, not sycophantic

Rules:
- Never start with "I am writing to apply for"
- Never use "I am passionate about"
- Never use "I am excited to"
- Be specific — generic cover letters are rejected immediately
- Draw only from real experience in the CV chunks provided
- Length: {cover_letter_length} means short=3 paragraphs, medium=4 paragraphs, long=5 paragraphs
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _client() -> AsyncClient:
    return AsyncClient(host=settings.ollama_host)


# ── Generation steps ──────────────────────────────────────────────────────────

async def run_gap_analysis(
    cv_chunks: list[str],
    job: dict,
    preferences: dict,
) -> dict:
    """Step 2: Analyse candidate fit against the job using Ollama structured output."""
    prompt = GAP_ANALYSIS_PROMPT.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        seniority=job.get("seniority", "unknown"),
        skills_required=json.dumps(json.loads(job.get("skills_required", "[]"))),
        skills_preferred=json.dumps(json.loads(job.get("skills_preferred", "[]"))),
        description_summary=job.get("description_clean", "")[:500],
        cv_chunks="\n\n".join(cv_chunks),
        target_roles=json.dumps(json.loads(preferences.get("target_roles", "[]"))),
        skills_to_grow=json.dumps(json.loads(preferences.get("skills_to_grow", "[]"))),
        tone_preference=preferences.get("tone_preference", "professional"),
        extra_context=preferences.get("extra_context") or "None provided",
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = await _client().chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format=GapAnalysis.model_json_schema(),
            )
            return json.loads(response['message']['content'])
        except json.JSONDecodeError as exc:
            logger.warning("Gap analysis JSON error (attempt %d): %s", attempt + 1, exc)
            last_error = exc
        except Exception as exc:
            logger.warning("Ollama error in gap analysis (attempt %d): %s", attempt + 1, exc)
            last_error = exc

    raise RuntimeError(f"Gap analysis failed after 2 attempts: {last_error}") from last_error


async def run_resume_tailoring(
    gap_analysis: dict,
    cv_chunks: list[str],
    cv_parsed_json: str,
    job: dict,
    preferences: dict,
) -> dict:
    """Step 3: Produce a tailored resume JSON using Ollama structured output."""
    prompt = RESUME_TAILORING_PROMPT.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        seniority=job.get("seniority", "unknown"),
        strategy=gap_analysis.get("strategy", ""),
        strengths_to_emphasise=json.dumps(gap_analysis.get("strengths_to_emphasise", [])),
        reframe_opportunities=json.dumps(gap_analysis.get("reframe_opportunities", [])),
        ats_keywords=json.dumps(json.loads(job.get("ats_keywords", "[]"))),
        cv_chunks="\n\n".join(cv_chunks),
        cv_parsed_json=cv_parsed_json,
        tone_preference=preferences.get("tone_preference", "professional"),
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = await _client().chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format=ResumeJson.model_json_schema(),
            )
            return json.loads(response['message']['content'])
        except json.JSONDecodeError as exc:
            logger.warning("Resume tailoring JSON error (attempt %d): %s", attempt + 1, exc)
            last_error = exc
        except Exception as exc:
            logger.warning("Ollama error in resume tailoring (attempt %d): %s", attempt + 1, exc)
            last_error = exc

    raise RuntimeError(f"Resume tailoring failed after 2 attempts: {last_error}") from last_error


async def run_cover_letter(
    gap_analysis: dict,
    cv_chunks: list[str],
    job: dict,
    preferences: dict,
) -> str:
    """Step 4: Generate a cover letter as plain text via Ollama chat."""
    prompt = COVER_LETTER_PROMPT.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location") or "Not specified",
        match_score=gap_analysis.get("match_score", 0),
        strengths_to_emphasise=json.dumps(gap_analysis.get("strengths_to_emphasise", [])),
        strategy=gap_analysis.get("strategy", ""),
        extra_context=preferences.get("extra_context") or "None provided",
        cv_chunks="\n\n".join(cv_chunks),
        tone_preference=preferences.get("tone_preference", "professional"),
        seniority_target=preferences.get("seniority_target", "senior"),
        cover_letter_length=preferences.get("cover_letter_length", "medium"),
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = await _client().chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response['message']['content'].strip()
        except Exception as exc:
            logger.warning("Ollama error in cover letter (attempt %d): %s", attempt + 1, exc)
            last_error = exc

    raise RuntimeError(f"Cover letter generation failed after 2 attempts: {last_error}") from last_error


# ── ATS scoring ───────────────────────────────────────────────────────────────

def calculate_ats_score(resume_json: dict, ats_keywords: list[str]) -> dict:
    """Score how many ATS keywords appear in the tailored resume text."""
    resume_text = " ".join([
        resume_json.get("summary", ""),
        *[b for exp in resume_json.get("experiences", []) for b in exp.get("bullets", [])],
        *resume_json.get("skills", {}).get("technical", []),
        *resume_json.get("skills", {}).get("tools", []),
    ]).lower()

    matched = [kw for kw in ats_keywords if kw.lower() in resume_text]
    missing = [kw for kw in ats_keywords if kw.lower() not in resume_text]
    score = round(len(matched) / len(ats_keywords) * 100) if ats_keywords else 0

    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "total_keywords": len(ats_keywords),
    }
