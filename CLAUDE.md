# CLAUDE.md — JobHunter App Specification

> Read this file at the start of every session before writing any code.
> This is the single source of truth for the entire project.
> Do not deviate from the architecture, stack, or conventions defined here.

---

## 1. Project Overview

JobHunter is a personal, local-first web app that helps a Data/ML engineer find and apply to relevant jobs. The user pastes a job description, the app parses it, matches it against their stored profile (CV + preferences), generates a tailored ATS-optimised resume and cover letter using a local Ollama model, and logs the application to a simple tracker.

**Who it is for:** Single user initially, multi-profile architecture from day one.
**Current phase:** MVP — manual paste flow only. No job board automation yet.
**Core value:** Paste a JD → get a tailored resume + cover letter in under 60 seconds.

---

## 2. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Backend | Python + FastAPI | FastAPI 0.115.0 |
| Backend runtime | Uvicorn | 0.30.0 |
| ORM | SQLAlchemy (async) | 2.0.35 |
| Migrations | Alembic | 1.13.3 |
| Validation | Pydantic + pydantic-settings | 2.9.0 |
| Database | SQLite + sqlite-vec | sqlite-vec 0.1.6 |
| AI | Ollama (local, free) | ollama 0.3.3 |
| AI model | llama3.2 (default, configurable via OLLAMA_MODEL in .env) | local, no API |
| Embeddings | sentence-transformers | 3.2.0 |
| Embedding model | all-MiniLM-L6-v2 | local, no API |
| PDF parsing | pdfplumber | 0.11.4 |
| Word export | python-docx | 1.1.2 |
| Fuzzy matching | rapidfuzz | 3.10.0 |
| Encoding fix | ftfy | latest |
| HTTP client | httpx | 0.27.0 |
| Env config | python-dotenv | 1.0.1 |
| File uploads | python-multipart | 0.0.12 |
| Frontend | React + Vite | React 18.3.1 |
| Styling | TailwindCSS | 3.4.13 |
| HTTP client (FE) | Axios | 1.7.7 |
| Routing (FE) | React Router | 6.27.0 |

**Ports:**
- Backend: `localhost:8000`
- Frontend: `localhost:5173`

**Never introduce a library not listed here without asking first.**

---

## 3. Folder Structure

```
jobhunter/
│
├── CLAUDE.md                      ← this file
├── .env                           ← ANTHROPIC_API_KEY=sk-... (never commit)
├── .gitignore                     ← exclude .env, jobhunter.db, __pycache__, node_modules
├── requirements.txt               ← all Python deps pinned
├── jobhunter.db                   ← created on first run, never commit
├── README.md
│
├── backend/
│   ├── main.py                    ← FastAPI app factory — create_app()
│   ├── database.py                ← SQLAlchemy async engine, session, sqlite-vec init
│   ├── config.py                  ← reads .env, exposes Settings object via pydantic-settings
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py              ← GET /health, GET /settings, PATCH /settings
│   │   ├── profile.py             ← all /profiles/* endpoints
│   │   ├── jobs.py                ← all /jobs/* endpoints
│   │   ├── generate.py            ← all /generate/* endpoints
│   │   └── tracker.py             ← all /tracker/* endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parser.py              ← CV PDF parsing (pdfplumber) + JD text cleaning
│   │   ├── embedder.py            ← sentence-transformers wrapper, chunk + embed CV
│   │   ├── rag.py                 ← cosine similarity retrieval against cv_chunks
│   │   ├── generator.py           ← all Claude API calls (gap analysis, resume, cover letter)
│   │   └── docx_generator.py      ← ATS-safe .docx generation from resume JSON
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── db.py                  ← SQLAlchemy ORM models (all tables)
│   │   └── schemas.py             ← Pydantic request/response schemas
│   │
│   └── alembic/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/              ← migration scripts live here
│
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx               ← React entry point
│       ├── App.jsx                ← router + layout + profile switcher
│       ├── api/
│       │   └── client.js          ← axios instance pointing to localhost:8000
│       ├── pages/
│       │   ├── Paste.jsx          ← job description paste + parse + trigger generation
│       │   ├── Profile.jsx        ← profile create, view, edit, preferences form
│       │   ├── Review.jsx         ← gap analysis + diff view + cover letter + approve
│       │   └── Tracker.jsx        ← application log table + search + document links
│       └── components/
│           ├── ProfileSwitcher.jsx ← dropdown in header to switch active profile
│           ├── DiffView.jsx        ← side-by-side original vs tailored resume
│           ├── AtsPanel.jsx        ← ATS score, matched/missing keywords, format check
│           └── GapAnalysisPanel.jsx ← match score, gaps, strategy, red flags
```

---

## 4. Database Schema

All tables live in `jobhunter.db`. Use SQLAlchemy async ORM for all queries. Never write raw SQL strings in routers — put all DB logic in services or dedicated query functions.

### profiles
```sql
CREATE TABLE profiles (
    id                INTEGER   PRIMARY KEY AUTOINCREMENT,
    name              TEXT      NOT NULL,
    cv_raw_text       TEXT      NOT NULL,
    cv_parsed_json    TEXT      NOT NULL,
    cv_filename       TEXT      NOT NULL,
    cv_hash           TEXT      NOT NULL,
    is_active         BOOLEAN   NOT NULL DEFAULT 0,
    is_deleted        BOOLEAN   NOT NULL DEFAULT 0,
    parse_attempts    INTEGER   NOT NULL DEFAULT 0,
    last_parse_error  TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### cv_chunks
```sql
CREATE TABLE cv_chunks (
    id             INTEGER   PRIMARY KEY AUTOINCREMENT,
    profile_id     INTEGER   NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    chunk_index    INTEGER   NOT NULL,
    chunk_type     TEXT      NOT NULL,  -- "experience"|"skills"|"education"|"summary"|"other"
    chunk_text     TEXT      NOT NULL,
    embedding      BLOB      NOT NULL,  -- 384-dim float32 serialised with numpy.ndarray.tobytes()
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### profile_preferences
```sql
CREATE TABLE profile_preferences (
    id                    INTEGER   PRIMARY KEY AUTOINCREMENT,
    profile_id            INTEGER   NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
    target_roles          TEXT      NOT NULL DEFAULT '[]',
    target_locations      TEXT      NOT NULL DEFAULT '[]',
    remote_preference     TEXT      NOT NULL DEFAULT 'any',  -- "remote"|"hybrid"|"onsite"|"any"
    salary_min_eur        INTEGER,
    company_size_pref     TEXT      NOT NULL DEFAULT 'any',  -- "startup"|"mid"|"enterprise"|"any"
    industries_to_avoid   TEXT      NOT NULL DEFAULT '[]',
    skills_to_grow        TEXT      NOT NULL DEFAULT '[]',
    tone_preference       TEXT      NOT NULL DEFAULT 'professional',  -- "professional"|"conversational"|"direct"
    cover_letter_length   TEXT      NOT NULL DEFAULT 'medium',  -- "short"|"medium"|"long"
    seniority_target      TEXT      NOT NULL DEFAULT 'senior',
    notice_period_weeks   INTEGER   NOT NULL DEFAULT 4,
    open_to_contract      BOOLEAN   NOT NULL DEFAULT 0,
    extra_context         TEXT,
    updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### embedding_runs
```sql
CREATE TABLE embedding_runs (
    id             INTEGER   PRIMARY KEY AUTOINCREMENT,
    profile_id     INTEGER   NOT NULL REFERENCES profiles(id),
    chunks_created INTEGER   NOT NULL,
    model_used     TEXT      NOT NULL,
    duration_ms    INTEGER   NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### jobs
```sql
CREATE TABLE jobs (
    id                TEXT      PRIMARY KEY,   -- sha256 hash of normalised company+title+location
    raw_text          TEXT      NOT NULL,
    title             TEXT      NOT NULL,
    company           TEXT      NOT NULL,
    location          TEXT,
    remote_type       TEXT,                    -- "remote"|"hybrid"|"onsite"|"unknown"
    salary_min        INTEGER,
    salary_max        INTEGER,
    salary_currency   TEXT,
    description_clean TEXT      NOT NULL,
    skills_required   TEXT      NOT NULL DEFAULT '[]',   -- JSON array
    skills_preferred  TEXT      NOT NULL DEFAULT '[]',   -- JSON array
    ats_keywords      TEXT      NOT NULL DEFAULT '[]',   -- JSON array, exact terms for ATS matching
    seniority         TEXT,                    -- "entry"|"mid"|"senior"|"lead"|"staff"|"unknown"
    posted_date       TEXT,
    fetched_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    extraction_ok     BOOLEAN   NOT NULL DEFAULT 1,
    extraction_error  TEXT
);
```

### job_hashes
```sql
CREATE TABLE job_hashes (
    hash        TEXT      PRIMARY KEY,
    job_id      TEXT      NOT NULL REFERENCES jobs(id),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### generation_results
```sql
CREATE TABLE generation_results (
    id                    INTEGER   PRIMARY KEY AUTOINCREMENT,
    job_id                TEXT      NOT NULL REFERENCES jobs(id),
    profile_id            INTEGER   NOT NULL REFERENCES profiles(id),
    gap_analysis_json     TEXT      NOT NULL,
    resume_json           TEXT      NOT NULL,
    cover_letter_text     TEXT      NOT NULL,
    chunks_used           TEXT      NOT NULL DEFAULT '[]',   -- JSON array of chunk ids
    ats_score             INTEGER,                           -- 0-100
    ats_matched           TEXT      NOT NULL DEFAULT '[]',   -- JSON array
    ats_missing           TEXT      NOT NULL DEFAULT '[]',   -- JSON array
    total_duration_ms     INTEGER   NOT NULL,
    resume_edited_json    TEXT,
    cover_letter_edited   TEXT,
    approved_at           TIMESTAMP,
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### document_snapshots
```sql
CREATE TABLE document_snapshots (
    id             INTEGER   PRIMARY KEY AUTOINCREMENT,
    generation_id  INTEGER   NOT NULL REFERENCES generation_results(id),
    doc_type       TEXT      NOT NULL,   -- "resume"|"cover_letter"
    content_json   TEXT,                 -- resume stored as JSON string
    content_text   TEXT,                 -- cover letter stored as plain text
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### applications
```sql
CREATE TABLE applications (
    id                   INTEGER   PRIMARY KEY AUTOINCREMENT,
    profile_id           INTEGER   NOT NULL REFERENCES profiles(id),
    job_id               TEXT      NOT NULL REFERENCES jobs(id),
    generation_id        INTEGER   NOT NULL REFERENCES generation_results(id),
    company              TEXT      NOT NULL,
    role                 TEXT      NOT NULL,
    location             TEXT,
    applied_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resume_snapshot_id   INTEGER   NOT NULL REFERENCES document_snapshots(id),
    cl_snapshot_id       INTEGER   NOT NULL REFERENCES document_snapshots(id)
);
```

### settings
```sql
CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
-- Seed rows: ('active_profile_id', ''), ('app_version', '0.1.0')
```

### startup_log
```sql
CREATE TABLE startup_log (
    id            INTEGER   PRIMARY KEY AUTOINCREMENT,
    started_at    TIMESTAMP NOT NULL,
    db_ok         BOOLEAN   NOT NULL,
    vec_ok        BOOLEAN   NOT NULL,
    api_key_ok    BOOLEAN   NOT NULL,
    app_version   TEXT      NOT NULL
);
```

### parse_log
```sql
CREATE TABLE parse_log (
    id                     INTEGER   PRIMARY KEY AUTOINCREMENT,
    job_id                 TEXT      REFERENCES jobs(id),
    raw_length_chars       INTEGER   NOT NULL,
    clean_length_chars     INTEGER   NOT NULL,
    extraction_ok          BOOLEAN   NOT NULL,
    extraction_duration_ms INTEGER   NOT NULL,
    was_duplicate          BOOLEAN   NOT NULL DEFAULT 0,
    created_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### generation_log
```sql
CREATE TABLE generation_log (
    id                    INTEGER   PRIMARY KEY AUTOINCREMENT,
    generation_id         INTEGER   NOT NULL REFERENCES generation_results(id),
    profile_id            INTEGER   NOT NULL,
    job_id                TEXT      NOT NULL,
    match_score           INTEGER,
    hard_gap_count        INTEGER,
    chunks_retrieved      INTEGER   NOT NULL,
    rag_duration_ms       INTEGER   NOT NULL,
    gap_analysis_ms       INTEGER   NOT NULL,
    resume_duration_ms    INTEGER   NOT NULL,
    cover_letter_ms       INTEGER   NOT NULL,
    total_duration_ms     INTEGER   NOT NULL,
    resume_was_edited     BOOLEAN   NOT NULL DEFAULT 0,
    cover_letter_edited   BOOLEAN   NOT NULL DEFAULT 0,
    approved              BOOLEAN   NOT NULL DEFAULT 0,
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### review_log
```sql
CREATE TABLE review_log (
    id                      INTEGER   PRIMARY KEY AUTOINCREMENT,
    generation_id           INTEGER   NOT NULL REFERENCES generation_results(id),
    profile_id              INTEGER   NOT NULL,
    time_to_approve_seconds INTEGER,
    resume_edit_count       INTEGER   NOT NULL DEFAULT 0,
    cl_edit_count           INTEGER   NOT NULL DEFAULT 0,
    downloaded_resume       BOOLEAN   NOT NULL DEFAULT 0,
    downloaded_cl           BOOLEAN   NOT NULL DEFAULT 0,
    approved                BOOLEAN   NOT NULL DEFAULT 0,
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. API Contracts

### Health and Settings

```
GET  /health
→ 200 { "status": "ok", "db": "connected", "version": "0.1.0" }

GET  /settings
→ 200 { "active_profile_id": 1 | null, "app_version": "0.1.0" }

PATCH /settings
← { "active_profile_id": 2 }
→ 200 { "active_profile_id": 2 }
```

### Profiles

```
POST   /profiles
← multipart/form-data: name (str) + cv_file (PDF)
→ 201  { "id": 1, "name": "ML Engineer", "status": "parsing" }

GET    /profiles/{id}/status
→ 200  { "id": 1, "status": "ready" | "parsing" | "failed" }

GET    /profiles
→ 200  [{ "id", "name", "is_active", "created_at" }]

GET    /profiles/{id}
→ 200  { "id", "name", "cv_parsed_json", "preferences", "created_at" }

PATCH  /profiles/{id}
← { "name": "string" }
→ 200  { updated profile }

DELETE /profiles/{id}
→ 204  (soft delete — sets is_deleted=true)

POST   /profiles/{id}/activate
→ 200  { "active_profile_id": 1 }

GET    /profiles/{id}/preferences
→ 200  { all preference fields }

PUT    /profiles/{id}/preferences
← { all preference fields }
→ 200  { updated preferences }

POST   /profiles/{id}/reembed
→ 202  { "message": "re-embedding started" }
```

### Jobs

```
POST  /jobs/paste
← { "text": "full job description", "profile_id": 1 }
→ 201 {
    "job_id", "title", "company", "location", "remote_type",
    "seniority", "salary_min", "salary_max", "salary_currency",
    "skills_required", "skills_preferred", "ats_keywords",
    "description_summary", "already_applied", "duplicate_of"
  }
→ 409 { "error": "duplicate", "job_id": "existing_id" }
→ 422 { "error": "too_short" | "too_long", "message": "..." }
→ 500 { "error": "extraction_failed", "message": "..." }

GET   /jobs/{job_id}
→ 200 { full job object }

GET   /jobs
→ 200 [{ id, title, company, location, fetched_at }]  ← last 50, newest first
```

### Generate

```
POST  /generate
← { "job_id": "abc123", "profile_id": 1 }
→ 202 { "generation_id": 42, "status": "running" }

GET   /generate/{generation_id}/status
→ 200 {
    "generation_id": 42,
    "status": "running" | "ready" | "failed",
    "step": "rag" | "gap_analysis" | "resume" | "cover_letter",
    "error": null | "string"
  }

GET   /generate/{generation_id}
→ 200 {
    "generation_id", "job_id",
    "gap_analysis": {
      "match_score", "matched_skills", "soft_gaps", "hard_gaps",
      "strengths_to_emphasise", "reframe_opportunities", "strategy", "red_flags"
    },
    "resume": { "summary", "experiences", "skills", "education" },
    "cover_letter": "string",
    "ats": { "score", "matched", "missing", "total_keywords" },
    "created_at"
  }

PATCH /generate/{generation_id}/resume
← { "resume_edited_json": { ... } }
→ 200 { "saved": true }

PATCH /generate/{generation_id}/cover-letter
← { "cover_letter_edited": "string" }
→ 200 { "saved": true }

POST  /generate/{generation_id}/approve
→ 201 {
    "application_id", "resume_snapshot_id",
    "cl_snapshot_id", "applied_at"
  }
→ 409 { "error": "already_approved", "application_id": 7 }
```

### Tracker

```
GET   /tracker
?profile_id=1&search=stripe&limit=50&offset=0
→ 200 {
    "total": 24,
    "applications": [{ "id", "company", "role", "location", "applied_at",
                       "resume_snapshot_id", "cl_snapshot_id" }]
  }

GET   /tracker/{application_id}/resume
→ 200 { full resume JSON snapshot }

GET   /tracker/{application_id}/cover-letter
→ 200 { "text": "full cover letter text" }

GET   /tracker/{application_id}/resume/download
→ 200 .docx file (application/vnd.openxmlformats-officedocument.wordprocessingml.document)
```

---

## 6. AI Prompts

### JD Extraction Prompt (Component 3 — parser.py)

```python
EXTRACTION_PROMPT = """
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
```

### CV Extraction Prompt (Component 2 — parser.py)

```python
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
```

### Gap Analysis Prompt (Component 4 — generator.py, Step 2)

```python
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
```

### Resume Tailoring Prompt (Component 4 — generator.py, Step 3)

```python
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
```

### Cover Letter Prompt (Component 4 — generator.py, Step 4)

```python
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
```

---

## 7. Key Service Logic

### ATS Scoring (services/generator.py)

```python
def calculate_ats_score(resume_json: dict, ats_keywords: list[str]) -> dict:
    resume_text = " ".join([
        resume_json.get("summary", ""),
        *[b for exp in resume_json["experiences"] for b in exp["bullets"]],
        *resume_json["skills"]["technical"],
        *resume_json["skills"]["tools"]
    ]).lower()

    matched = [kw for kw in ats_keywords if kw.lower() in resume_text]
    missing = [kw for kw in ats_keywords if kw.lower() not in resume_text]
    score = round(len(matched) / len(ats_keywords) * 100) if ats_keywords else 0

    return {"score": score, "matched": matched, "missing": missing,
            "total_keywords": len(ats_keywords)}
```

### CV Chunking Strategy (services/embedder.py)

Chunk by semantic section, not fixed character length.
Use Claude-parsed JSON structure to define chunk boundaries:
- One chunk per experience entry (title + company + dates + description + bullets)
- One chunk for the full skills section
- One chunk for the summary
- One chunk for education + certifications

Target: 10-30 chunks per CV.
Store embedding as: `numpy.ndarray.tobytes()` → BLOB column.
Retrieve embedding as: `numpy.frombuffer(blob, dtype=numpy.float32)`.

### RAG Retrieval (services/rag.py)

- Embed the full job description using all-MiniLM-L6-v2
- Use `normalize_embeddings=True` so dot product = cosine similarity
- Fetch all cv_chunks for the active profile_id
- Compute dot product between JD embedding and each chunk embedding
- Sort descending, return top 8 chunks
- No external vector DB — pure numpy in Python

### Generation Flow (services/generator.py)

All four steps run sequentially. Each step's output feeds the next.
Steps:
1. RAG retrieval — Python only, no Claude call
2. Gap analysis — Claude call, returns JSON
3. Resume tailoring — Claude call, uses gap analysis output, returns JSON
4. Cover letter — Claude call, uses gap analysis output, returns plain text
5. ATS scoring — Python only, no Claude call

Use `asyncio.gather` where steps can run in parallel (step 3 and 4 can run concurrently after step 2).

### .docx ATS Rules (services/docx_generator.py)

- Font: Calibri only, body 11pt, headings 13pt, name 16pt
- Single column — never use tables or text boxes for layout
- Section headings: SUMMARY, EXPERIENCE, SKILLS, EDUCATION (uppercase)
- Separator between title and company: pipe character `|`  not em dash
- No colour except pure black RGB(0,0,0)
- No images, icons, or graphics of any kind
- No header or footer regions for important content
- Margins: 0.5 inch top/bottom, 0.75 inch left/right
- Generate on demand from JSON — do not store .docx files permanently

---

## 8. Coding Rules and Conventions

### General
- Python files use snake_case. React files use PascalCase for components, camelCase for utilities.
- All async Python — use `async def` and `await` throughout the backend.
- Never write raw SQL strings — use SQLAlchemy ORM models.
- All DB sessions via dependency injection: `db: AsyncSession = Depends(get_db)`.
- All environment variables via the `Settings` object from `config.py` — never `os.environ` directly.
- Every router function has a docstring explaining what it does.
- Every service function has type hints on all parameters and return values.

### Error Handling
- Every Ollama call wrapped in try/except with one retry before failing.
- If sqlite-vec extension fails to load: log warning, continue, return 503 on any vector operation.
- If Ollama server is unreachable: app starts but returns 503 on any AI-dependent endpoint.
- Never return a Python traceback to the frontend — always return a structured JSON error.
- Error response shape: `{ "error": "error_code", "message": "human readable message" }`.

### Ollama API Calls
- Model: configured via `OLLAMA_MODEL` env var (default `llama3.2`) — read from `settings.ollama_model`.
- Host: configured via `OLLAMA_HOST` env var (default `http://localhost:11434`) — read from `settings.ollama_host`.
- JSON extraction calls: use `format=Schema.model_json_schema()` for structured outputs.
- Cover letter: plain `chat()` call with no `format=` — returns free text.
- Retry once on JSON parse failure or Ollama error.

### CORS
- Allow origin: `http://localhost:5173` only.
- Allow methods: `["GET", "POST", "PUT", "PATCH", "DELETE"]`.
- Allow headers: `["*"]`.

### Frontend
- All API calls go through `src/api/client.js` — never use fetch directly in components.
- Loading states for every async operation — no silent waits.
- Poll `/generate/{id}/status` every 2 seconds during generation — stop on "ready" or "failed".
- Poll `/profiles/{id}/status` every 2 seconds during CV parsing — stop on "ready" or "failed".
- Auto-save edits to resume and cover letter on blur with 1-second debounce.
- Never show a Python error message to the user — show friendly messages only.

### What Never to Do
- Never add a library not listed in the tech stack without explicit instruction.
- Never build features outside the current session scope.
- Never store the .env file or jobhunter.db in git.
- Never hard-code the API key anywhere — always read from environment.
- Never invent CV experience in generation prompts — this is the most critical rule.
- Never use two-column layout in .docx output — ATS parsers cannot read it.
- Never add authentication — this app is local only, no auth needed.
- Never use localStorage or sessionStorage in the frontend.

---

## 9. Build Status

Track what is complete. Update this section at the end of every session.

| Component | Status | Notes |
|---|---|---|
| Component 1 — Project setup + skeleton | ✅ Complete | Python 3.14 requires >=version pins; sqlite-vec loads but enable_load_extension needs sync conn workaround (deferred to RAG session) |
| Component 2 — Profile system (DB + parsing) | ✅ Complete | Background task runs in daemon thread (asyncio.run) with own engine — Starlette 1.0 cancels anyio-scoped tasks; Ollama takes ~40s for CV parse with llama3.2 |
| Component 2 — Profile system (embeddings) | ✅ Complete | all-MiniLM-L6-v2 loaded once at module level; semantic chunking (experience/skills/education/summary); 384-dim float32 BLOB; EmbeddingRun logged; reembed endpoint wired |
| Component 2 — Profile system (preferences API) | ⬜ Not started | |
| Component 3 — Job paste + parse | ⬜ Not started | |
| Component 4 — RAG retrieval | ⬜ Not started | |
| Component 4 — Gap analysis | ⬜ Not started | |
| Component 4 — Resume tailoring + ATS | ⬜ Not started | |
| Component 4 — Cover letter | ⬜ Not started | |
| Component 5 — Generation storage + API | ⬜ Not started | |
| Component 5 — React setup + routing | ⬜ Not started | |
| Component 5 — Profile page UI | ⬜ Not started | |
| Component 5 — Paste page UI | ⬜ Not started | |
| Component 5 — Review page UI | ⬜ Not started | |
| Component 5 — Tracker page UI | ⬜ Not started | |
| End to end test | ⬜ Not started | |

---

## 10. Session Prompts

Use these exact prompts to start each Claude Code session.

### Session 1 — Project setup
```
Read CLAUDE.md fully before starting.
Today we are building Component 1 — project setup and backend skeleton.
Tasks:
1. Create the exact folder structure from CLAUDE.md section 3
2. Create requirements.txt with all packages from section 2
3. Create backend/config.py reading ANTHROPIC_API_KEY from .env using pydantic-settings
4. Create backend/database.py with async SQLAlchemy engine, session factory, and sqlite-vec init
5. Create backend/main.py with create_app() factory, CORS config, and router registration
6. Create backend/routers/health.py with GET /health and GET/PATCH /settings endpoints
7. Create all SQLAlchemy ORM models in backend/models/db.py from schema in section 4
8. Create all Pydantic schemas in backend/models/schemas.py
9. Run the app and confirm GET /health returns {"status":"ok","db":"connected","version":"0.1.0"}
Do not build anything outside this list.
```

### Session 2 — Profile DB + CV parsing
```
Read CLAUDE.md fully. Component 1 is complete.
Today we are building Component 2 part 1 — profile creation, CV upload, and parsing.
Tasks:
1. Create backend/services/parser.py with pdfplumber CV extraction and text cleaning
2. Create backend/routers/profile.py with POST /profiles (multipart upload)
3. Implement async background parsing after upload using FastAPI BackgroundTasks
4. Implement the CV extraction Claude call using CV_EXTRACTION_PROMPT from section 6
5. Store parsed result in profiles table, set status to ready
6. Implement GET /profiles/{id}/status endpoint
7. Test: upload a PDF, poll status, confirm cv_parsed_json is populated correctly
Do not implement embeddings yet — that is next session.
```

### Session 3 — Embeddings
```
Read CLAUDE.md fully. Components 1 and 2 part 1 are complete.
Today we are building Component 2 part 2 — CV chunking and embedding.
Tasks:
1. Create backend/services/embedder.py loading all-MiniLM-L6-v2 once at module level
2. Implement chunk_cv() using the chunking strategy in section 7 — semantic sections not fixed size
3. Implement embed_chunks() storing each embedding as numpy bytes in cv_chunks table
4. Wire embedding into the background task after CV parsing completes
5. Implement POST /profiles/{id}/reembed endpoint
6. Test: after upload confirm cv_chunks rows exist with correct chunk_types
Do not implement RAG retrieval yet — that is Component 4.
```

### Session 4 — Preferences API
```
Read CLAUDE.md fully. Components 1 and 2 parts 1-2 are complete.
Today we are building Component 2 part 3 — preferences endpoints.
Tasks:
1. Add GET /profiles, GET /profiles/{id}, PATCH /profiles/{id}, DELETE /profiles/{id}
2. Add POST /profiles/{id}/activate — switches active profile, only one active at a time
3. Add GET /profiles/{id}/preferences and PUT /profiles/{id}/preferences
4. Test all endpoints with curl or the FastAPI /docs interface
```

### Session 5 — Job paste and parse
```
Read CLAUDE.md fully. Component 2 is complete.
Today we are building Component 3 — job paste and parse.
Tasks:
1. Create backend/services/parser.py additions for JD cleaning (clean_jd_text, validate_jd_text)
2. Create backend/routers/jobs.py with POST /jobs/paste
3. Implement dedup check using sha256 hash of normalised company+title+location
4. Implement already-applied check against applications table filtered by profile_id
5. Implement the JD extraction Claude call using EXTRACTION_PROMPT from section 6
6. Store result in jobs and job_hashes tables, write to parse_log
7. Implement GET /jobs/{job_id} and GET /jobs
8. Test: paste a real job description, confirm structured output is correct
```

### Session 6 — RAG + Gap analysis
```
Read CLAUDE.md fully. Components 1-3 are complete.
Today we are building Component 4 parts 1 and 2 — RAG retrieval and gap analysis.
Tasks:
1. Create backend/services/rag.py with retrieve_relevant_chunks() as described in section 7
2. Create backend/services/generator.py with run_gap_analysis() using GAP_ANALYSIS_PROMPT
3. Create backend/routers/generate.py with POST /generate — starts async generation
4. Implement generation status tracking in generation_results table
5. Implement GET /generate/{id}/status
6. Test: trigger generation for a parsed job, confirm gap_analysis_json is populated
```

### Session 7 — Resume + Cover letter generation
```
Read CLAUDE.md fully. RAG and gap analysis are complete.
Today we are building Component 4 parts 3 and 4 — resume tailoring and cover letter.
Tasks:
1. Implement run_resume_tailoring() in generator.py using RESUME_TAILORING_PROMPT
2. Implement run_cover_letter() in generator.py using COVER_LETTER_PROMPT
3. Run steps 3 and 4 concurrently using asyncio.gather after gap analysis completes
4. Implement calculate_ats_score() from section 7
5. Store all results in generation_results table including ats_score, ats_matched, ats_missing
6. Implement GET /generate/{id} returning full result
7. Implement PATCH /generate/{id}/resume and PATCH /generate/{id}/cover-letter
8. Implement POST /generate/{id}/approve — creates document snapshots and application record atomically
9. Test full generation end to end from job_id to approved application
```

### Session 8 — React setup + Profile page
```
Read CLAUDE.md fully. All backend components are complete.
Today we are building the React frontend — setup and Profile page.
Tasks:
1. Create frontend/ with Vite + React + TailwindCSS using exact versions from section 2
2. Create src/api/client.js axios instance pointing to localhost:8000
3. Create App.jsx with React Router routes: /, /profile, /paste, /review/:id, /tracker
4. Create ProfileSwitcher component in header — fetches GET /profiles, calls POST /profiles/{id}/activate
5. Create Profile page — CV upload form, polling for parse status, preferences form
6. Style with Tailwind — clean, minimal, functional. No decorative complexity.
7. Test: create a profile, upload CV, fill preferences, confirm data saves correctly
```

### Session 9 — Paste page + Review page
```
Read CLAUDE.md fully.
Today we are building the Paste page and Review page.
Tasks:
1. Create Paste.jsx — textarea for JD, submit calls POST /jobs/paste then POST /generate, polls status
2. Show generation progress steps: "Analysing fit... Tailoring resume... Writing cover letter..."
3. On ready redirect to /review/:generation_id
4. Create Review.jsx with three panels: GapAnalysisPanel, DiffView, cover letter textarea
5. Create GapAnalysisPanel.jsx — match score, matched/missing skills, strategy, red flags, ATS panel
6. Create AtsPanel.jsx — score percentage, matched keywords green, missing keywords red, critical flag
7. Create DiffView.jsx — original CV bullets left, tailored bullets right, changes highlighted, editable
8. Auto-save edits on blur with 1-second debounce to PATCH endpoints
9. Approve button calls POST /generate/{id}/approve, redirects to /tracker on success
```

### Session 10 — Tracker page + docx download
```
Read CLAUDE.md fully.
Today we are building the Tracker page and docx generation.
Tasks:
1. Create Tracker.jsx — table of applications, search bar, CV and CL buttons per row
2. CV button opens modal with resume JSON rendered as readable text
3. CL button opens modal with cover letter plain text
4. Download button calls GET /tracker/{id}/resume/download — receives .docx file
5. Create backend/services/docx_generator.py with generate_ats_resume_docx() following ATS rules in section 7
6. Wire docx generation into GET /tracker/{id}/resume/download endpoint — generate on demand, stream file
7. End to end test: paste JD → generate → review → approve → find in tracker → download .docx
8. Update build status in CLAUDE.md section 9
```

---

*Last updated: project start. Update after every session.*
