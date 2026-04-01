import os
import json
import base64
import tempfile

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from pinecone import Pinecone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from simple_salesforce import Salesforce
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Kiddom Sales Process GPT Backend")

# --- Clients ---

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
INDEX_NAME = "kiddom-sales-docs"

SYSTEM_INSTRUCTION = open("system_instruction.txt").read()

DOC_IDS = [
    "1Ty4Roqr2zbX-MAurFUblu_Bw0QluURlke0hTIC6Btak",  # Sales Cheatsheet for Rostering (copy)
    "14zYzSArxiyp9frKQIHVcOCGtrh_TGsA9HRcKHmfacQs",  # AE<>CSM Handoff Process (copy)
    "1iIrcpoXgAcGCd3qWO9mmsmZV-WoOW9Qm3ozxP2y2PGY",  # Rostering Announcement
    "1dG2dZdoR6DzQgF9sX18T4CQ_vODsnza8GRK-uTL78MM",  # Early Access Process
]


def _get_drive_service():
    creds_b64 = os.environ["GOOGLE_CREDENTIALS"]
    creds_json = json.loads(base64.b64decode(creds_b64))
    creds = service_account.Credentials.from_service_account_info(
        creds_json, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def _get_docs_service():
    creds_b64 = os.environ["GOOGLE_CREDENTIALS"]
    creds_json = json.loads(base64.b64decode(creds_b64))
    creds = service_account.Credentials.from_service_account_info(
        creds_json, scopes=["https://www.googleapis.com/auth/documents.readonly"]
    )
    return build("docs", "v1", credentials=creds)


def _read_google_doc(doc_id: str) -> str:
    """Read a Google Doc and return its plain text content."""
    service = _get_docs_service()
    doc = service.documents().get(documentId=doc_id).execute()
    text = ""
    for element in doc.get("body", {}).get("content", []):
        for para_element in element.get("paragraph", {}).get("elements", []):
            text_run = para_element.get("textRun", {})
            text += text_run.get("content", "")
    return text


def _get_sfdc_client():
    return Salesforce(
        username=os.environ["SFDC_USER"],
        password=os.environ["SFDC_PASS"],
        security_token=os.environ["SFDC_TOKEN"],
    )


def _embed(text: str) -> list[float]:
    resp = openai_client.embeddings.create(
        input=text, model="text-embedding-3-small"
    )
    return resp.data[0].embedding


def _query_pinecone(query: str, top_k: int = 5) -> str:
    index = pc.Index(INDEX_NAME)
    vector = _embed(query)
    results = index.query(vector=vector, top_k=top_k, include_metadata=True)
    chunks = []
    for match in results.matches:
        chunks.append(match.metadata.get("text", ""))
    return "\n\n---\n\n".join(chunks)


def _fetch_live_docs() -> str:
    """Fetch all canonical Google Docs and return combined text."""
    texts = []
    for doc_id in DOC_IDS:
        try:
            text = _read_google_doc(doc_id)
            texts.append(text)
        except Exception as e:
            texts.append(f"[Error fetching doc {doc_id}: {e}]")
    return "\n\n---\n\n".join(texts)


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    message: str
    use_live_docs: bool = True


class ChatResponse(BaseModel):
    reply: str
    sources: list[str]


class HandoffRequest(BaseModel):
    opportunity_id: str


class HandoffResponse(BaseModel):
    summary: str
    checklist: list[str]


class RosteringRequest(BaseModel):
    question: str


# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main chat endpoint — answers sales process questions using docs + Pinecone."""
    # Get context from Pinecone and/or live docs
    pinecone_context = ""
    try:
        pinecone_context = _query_pinecone(req.message)
    except Exception:
        pass

    live_context = ""
    if req.use_live_docs:
        try:
            live_context = _fetch_live_docs()
        except Exception:
            pass

    context = ""
    if live_context:
        context += f"## Live Document Content\n\n{live_context}\n\n"
    if pinecone_context:
        context += f"## Indexed Document Excerpts\n\n{pinecone_context}\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "system", "content": f"Reference material:\n\n{context}"},
        {"role": "user", "content": req.message},
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
    )

    reply = response.choices[0].message.content
    sources = ["Sales Cheatsheet for Rostering", "Rostering Announcement 1/27/25", "AE<>CSM Handoff Process"]

    return ChatResponse(reply=reply, sources=sources)


@app.post("/prepare_handoff", response_model=HandoffResponse)
def prepare_handoff(req: HandoffRequest):
    """Pull opportunity data from SFDC and generate a handoff summary."""
    try:
        sf = _get_sfdc_client()
        opp = sf.Opportunity.get(req.opportunity_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch opportunity: {e}")

    opp_name = opp.get("Name", "Unknown")
    account_name = opp.get("Account", {}).get("Name", "Unknown") if isinstance(opp.get("Account"), dict) else "Unknown"
    amount = opp.get("Amount", "N/A")
    close_date = opp.get("CloseDate", "N/A")
    stage = opp.get("StageName", "N/A")

    # Get handoff process from docs
    handoff_context = ""
    try:
        handoff_context = _query_pinecone("AE CS handoff process steps checklist")
    except Exception:
        pass

    prompt = f"""Based on this Salesforce opportunity and our handoff process docs, generate a handoff summary and checklist.

Opportunity: {opp_name}
Account: {account_name}
Amount: {amount}
Close Date: {close_date}
Stage: {stage}

Handoff Process Reference:
{handoff_context}

Return a brief summary paragraph and a checklist of handoff steps."""

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": prompt},
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
    )

    reply = response.choices[0].message.content
    lines = reply.strip().split("\n")
    summary_lines = []
    checklist = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "☐ ", "□ ")) or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in (".", ")")):
            checklist.append(stripped.lstrip("-*☐□ 0123456789.)").strip())
        elif stripped:
            summary_lines.append(stripped)

    return HandoffResponse(
        summary=" ".join(summary_lines) if summary_lines else reply,
        checklist=checklist if checklist else ["Review handoff docs for steps"],
    )


@app.post("/rostering_wizard")
def rostering_wizard(req: RosteringRequest):
    """Guided rostering assistance using the Sales Cheatsheet."""
    context = ""
    try:
        context = _query_pinecone(f"rostering {req.question}")
    except Exception:
        pass

    live_context = ""
    try:
        live_context = _read_google_doc(DOC_IDS[0])  # Sales Cheatsheet
    except Exception:
        pass

    combined = ""
    if live_context:
        combined += f"## Sales Cheatsheet (Live)\n\n{live_context}\n\n"
    if context:
        combined += f"## Indexed Excerpts\n\n{context}\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "system", "content": f"Rostering reference material:\n\n{combined}"},
        {"role": "user", "content": f"Rostering question: {req.question}"},
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
    )

    return {"answer": response.choices[0].message.content}
