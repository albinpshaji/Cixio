# Local RAG Engine

Local document question answering for pasted text and PDFs with a Next.js frontend,
Python/FastAPI backend, PostgreSQL + pgvector, and Ollama.

## Architecture

```text
Browser
  -> Next.js React frontend
  -> Python FastAPI backend
  -> Ollama + PostgreSQL/pgvector
```

The frontend lives in `app/page.tsx`. The Python backend lives in `backend/app`.

## Setup

Start PostgreSQL:

```bash
npm run db:up
```

Make sure Ollama is running and the models are available:

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

Start the Python API:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

After the first backend setup, you can also start the API from the repo root:

```bash
npm run api:dev
```

Start the Next.js frontend from the repo root:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Configuration

The frontend calls `http://localhost:8000` by default. Override it with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The backend defaults match the local Docker and Ollama setup. Copy
`backend/.env.example` to `backend/.env` if you want to override them.

## Features

- Paste plain text and ingest it into pgvector.
- Upload PDFs and store page-aware chunks.
- Ask grounded questions against stored chunks.
- Inspect retrieved source chunks and PDF page metadata.
