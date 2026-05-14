# JobHunter

A local-first AI job application assistant for Data/ML engineers. Paste a job description, get a tailored resume and cover letter — everything runs on your machine, no cloud APIs, no data leaves your device.

---

## What it does

1. **Paste a job description** — the app extracts the role, company, required skills, and ATS keywords
2. **Analyses your fit** — compares your CV against the role and produces a match score, gap analysis, and application strategy
3. **Generates tailored documents** — rewrites your resume bullets to match the role and writes a cover letter, using only experience from your real CV
4. **Review and edit** — side-by-side diff view shows original vs tailored bullets; click any bullet to edit inline, changes auto-save
5. **Approve and track** — snapshots both documents, logs the application, lets you download an ATS-safe `.docx` resume

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python + FastAPI |
| Database | SQLite + sqlite-vec |
| AI (LLM) | Ollama — llama3.2 (local, free) |
| Embeddings | sentence-transformers — all-MiniLM-L6-v2 (local) |
| PDF parsing | pdfplumber |
| Word export | python-docx |
| Frontend | React + Vite + TailwindCSS |

---

## Prerequisites

Install these before getting started:

| Tool | Download |
|---|---|
| Python 3.11+ | https://python.org |
| Node.js 18+ | https://nodejs.org |
| Ollama | https://ollama.ai |

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/Tarun-yadav777/jobhunter.git
cd jobhunter
```

**2. Pull the Ollama model**
```bash
ollama pull llama3.2
```

**3. Set up the Python virtual environment**
```bash
python -m venv .venv
```

Activate it:
- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Mac/Linux: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

**4. Install frontend dependencies**
```bash
cd frontend
npm install
cd ..
```

---

## Running the app

You need **two terminals** open at the same time.

**Terminal 1 — Backend**
```bash
cd jobhunter
.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate       # Mac/Linux
uvicorn backend.main:app --port 8000 --reload
```

Confirm it's running: open http://localhost:8000/health — you should see:
```json
{"status": "ok", "db": "connected", "version": "0.1.0"}
```

**Terminal 2 — Frontend**
```bash
cd jobhunter/frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

> Make sure Ollama is also running. Check by visiting http://localhost:11434. If it's not running, start it with `ollama serve`.

---

## First-time setup

1. Go to **Profile** in the navigation
2. Click **New profile**, enter a name, and upload your CV as a PDF
3. Wait ~30–60 seconds for Ollama to parse your CV
4. Fill in your **preferences** (target roles, tone, notice period, etc.)
5. Click **Set active** on your profile

---

## Usage

### Generate an application
1. Go to **Paste JD**
2. Paste a full job description into the text area
3. Click **Parse & Generate**
4. Watch the progress — it runs three steps: matching your CV, analysing fit, then tailoring the resume and cover letter
5. Generation takes **2–10 minutes** depending on your machine

### Review and approve
- The **left sidebar** shows your fit score, matched skills, gaps, and strategy
- The **right panel** shows your tailored resume — click any bullet to edit it
- Below the resume is your **cover letter** — click to edit
- All edits auto-save when you click away
- Click **Approve & log application** when you're happy

### Track applications
- Go to **Tracker** to see all logged applications
- Click **Resume** to view the saved resume snapshot
- Click **Cover letter** to view the saved cover letter
- Click **.docx** to download an ATS-safe Word document ready to send

---

## Improving output quality

The quality of generated content depends heavily on the Ollama model. The default `llama3.2` is a small 3B model — fast but limited. To improve quality, switch to a larger model in a `.env` file in the project root:

```
OLLAMA_MODEL=llama3.1:8b
```

Then pull the model and restart the backend:
```bash
ollama pull llama3.1:8b
```

Larger models require more RAM — `8b` needs ~8GB, `70b` needs ~40GB.

You can also improve output by:
- Filling in the **Extra context** field in your profile preferences (2–3 sentences about your background and goals)
- Using the inline edit tools on the Review page to refine bullets before approving

---

## Project structure

```
jobhunter/
├── backend/
│   ├── main.py              — FastAPI app
│   ├── routers/             — API endpoints
│   ├── services/            — AI, parsing, RAG, docx generation
│   └── models/              — Database models and schemas
├── frontend/
│   └── src/
│       ├── pages/           — Paste, Profile, Review, Tracker
│       ├── components/      — DiffView, GapAnalysisPanel, AtsPanel
│       └── api/client.js    — Axios API client
├── requirements.txt
└── jobhunter.db             — created automatically on first run
```

---

## Notes

- Everything runs locally — no data is sent to any external service
- The SQLite database (`jobhunter.db`) is created automatically on first run
- `.env` and `jobhunter.db` are excluded from git
- This is an MVP — single user, manual paste flow only
