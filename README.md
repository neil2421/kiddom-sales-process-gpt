# Kiddom Sales Process GPT

Internal Custom GPT backend for Kiddom's Sales and Customer Success teams. Answers questions about rostering workflows, AE→CS handoffs, and sales processes using canonical Google Drive docs.

## Architecture
- **FastAPI** backend with `/chat`, `/prepare_handoff`, and `/rostering_wizard` endpoints
- **Pinecone** vector store for semantic search over indexed process docs
- **Google Docs API** for live document fetching at query time
- **Salesforce API** for pulling opportunity data (handoff prep)
- **OpenAI GPT-4o** for response generation
- **Google Cloud Run** for hosting

## Quick Start

```bash
# Clone
git clone https://github.com/neil2421/kiddom-sales-process-gpt.git
cd kiddom-sales-process-gpt

# Install deps
pip install -r requirements.txt

# Set up env vars (copy and fill in)
cp .env.template .env

# Index docs into Pinecone
python index_drive.py

# Run locally
uvicorn app:app --reload --port 8080
```

## Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/chat` | POST | Main Q&A — answers sales process questions |
| `/prepare_handoff` | POST | Generates handoff summary from SFDC opportunity |
| `/rostering_wizard` | POST | Guided rostering assistance |

## Deployment
Push to `main` triggers automatic deployment to Cloud Run via GitHub Actions. See [docs/deploy_gcp.md](docs/deploy_gcp.md).

## Indexing Docs
See [docs/INDEX_DOCS.md](docs/INDEX_DOCS.md) for details on indexing Google Drive docs into Pinecone.
