# Indexing Google Drive Docs into Pinecone

## Overview
`index_drive.py` reads canonical Kiddom process docs from Google Drive, chunks them, generates embeddings via OpenAI, and stores them in a Pinecone serverless index.

## Prerequisites
Set these environment variables (or create a `.env` file from `.env.template`):
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_ENV` (e.g., `us-east-1`)
- `GOOGLE_CREDENTIALS` (base64-encoded service account JSON)

The Google service account must have **Viewer** access to each Google Doc.

## Running
```bash
pip install -r requirements.txt
python index_drive.py
```

## What It Does
1. Connects to Google Docs API using the service account
2. Reads each canonical doc as plain text
3. Splits text into ~500-token chunks with 50-token overlap
4. Generates embeddings using `text-embedding-3-small`
5. Upserts all vectors to the `kiddom-sales-docs` Pinecone index

## Indexed Documents
| Document | Doc ID | Priority |
|----------|--------|----------|
| Sales Cheatsheet for Rostering | `1ODSFoUgwyKW67YynBoInAIHkE4PYGPF0bIrfCKmHdrk` | High |
| AE<>CSM Handoff Process | `1xKIKGwCH1Tbr_w-YDEH7jop-RfUwDLNemUt55InH78k` | Medium |
| Rostering Announcement 1/27/25 | `1iIrcpoXgAcGCd3qWO9mmsmZV-WoOW9Qm3ozxP2y2PGY` | Medium |

## Re-indexing
Run `index_drive.py` again any time docs are updated. It upserts (overwrites) existing vectors by ID.
