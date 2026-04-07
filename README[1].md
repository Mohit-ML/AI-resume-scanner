# AI Resume Scanner

Upload a PDF resume and get instant AI-powered skill analysis, job description matching, and actionable improvement suggestions.

## Features
- PDF text extraction via `pdfplumber`
- Skill detection across 8 categories (programming, web, backend, DB, cloud, ML/AI, tools, soft skills)
- Job description match scoring with gap analysis
- Contact info & education extraction
- Improvement suggestions

## Quick Start

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open → http://localhost:8000

## Stack
- **Backend**: FastAPI + pdfplumber
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks)
- **No external AI API needed** — fully local pattern matching
