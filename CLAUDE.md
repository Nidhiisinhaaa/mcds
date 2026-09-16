# Multilingual Clinical Dialogue System

## What this is
An AI-powered lifestyle assessment web app. A patient describes symptoms by voice or text in their own language. An AI assistant asks about 8 lifestyle areas (sleep, exercise, diet, water intake, stress, sitting hours, smoking, alcohol), extracts structured answers, computes a Lifestyle Wellness Score, detects lifestyle-related risk factors, and generates guideline-grounded recommendations. A doctor reviews everything as a structured clinical summary and PDF report.

This is a screening and documentation aid. It never diagnoses, never prescribes or names medications, and always defers to the doctor.

## Stack (do not substitute without asking)
- Backend: Python 3.10.11 (pinned to the installed interpreter — do not require a newer version), Django 5, Django REST Framework, djangorestframework-simplejwt, django-cors-headers, python-dotenv
- Database: SQLite3 (use JSONField for structured data)
- LLM + speech: Groq API via the official `groq` Python SDK
  - Chat model id from env GROQ_CHAT_MODEL (default: llama-3.3-70b-versatile)
  - Speech-to-text model id from env GROQ_STT_MODEL (default: whisper-large-v3)
- Medical NLP: scispaCy (en_ner_bc5cdr_md) + regex number parsing
- RAG: ChromaDB (persistent, local) with its default ONNX all-MiniLM-L6-v2 embedding function. Do NOT install torch or sentence-transformers. The backend must stay torch-free so it runs on a small VPS.
- PDF: WeasyPrint
- Frontend: Next.js (App Router), JavaScript/JSX ONLY. No TypeScript, no .ts/.tsx files, no tsconfig.json. Tailwind CSS. Recharts for charts.
- Deploy target: Ubuntu VPS, Nginx + Gunicorn + systemd, GitHub Actions over SSH.

## Repo layout
/backend   Django project (config/) + apps: accounts, consultations, assessment, knowledge, reports, and a core/ package for shared services
/frontend  Next.js app
/deploy    nginx, systemd and CI files
/docs      architecture notes, scoring table

## Conventions
- Secrets live in backend/.env and frontend/.env.local. Commit only .env.example files.
- Every Groq call goes through backend/core/services/groq_client.py. The frontend never calls Groq.
- GROQ_MOCK=1 makes every Groq call return deterministic fixture data, so tests and local dev work offline.
- Every LLM call that returns data uses JSON mode and is validated with a pydantic model. On validation failure, retry once with the validation error appended, then fail gracefully.
- Deterministic logic (scoring, risk rules, BMI) lives in plain Python, never in prompts.
- Internal data is English. Patient-facing text is in the patient's chosen language.
- Write pytest + pytest-django tests for services and APIs and keep them passing.
- Design system for this product is "Bedside Teal" (defined in Phase 6). Do not use the CodeAj Obsidian Gold brand here.

## Working style
Build phase by phase. At the end of each phase: run migrations and tests, list files created or changed, explain how to verify manually, then STOP and wait for my go-ahead.