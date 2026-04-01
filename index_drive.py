"""
Index canonical Kiddom Google Drive docs into Pinecone.

Required env vars:
  OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV, GOOGLE_CREDENTIALS (base64)

Usage:
  python index_drive.py
"""

import os
import json
import base64

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import tiktoken

load_dotenv()

INDEX_NAME = "kiddom-sales-docs"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
CHUNK_SIZE = 500  # tokens per chunk
CHUNK_OVERLAP = 50

DOCS = [
    {
        "id": "1Ty4Roqr2zbX-MAurFUblu_Bw0QluURlke0hTIC6Btak",
        "name": "Sales Cheatsheet for Rostering",
        "category": "rostering,handoff",
        "priority": "high",
    },
    {
        "id": "14zYzSArxiyp9frKQIHVcOCGtrh_TGsA9HRcKHmfacQs",
        "name": "AE<>CSM Handoff Process",
        "category": "handoff",
        "priority": "medium",
    },
    {
        "id": "1iIrcpoXgAcGCd3qWO9mmsmZV-WoOW9Qm3ozxP2y2PGY",
        "name": "Rostering Announcement 1/27/25",
        "category": "rostering,support",
        "priority": "medium",
    },
]


def get_docs_service():
    creds_b64 = os.environ["GOOGLE_CREDENTIALS"]
    creds_json = json.loads(base64.b64decode(creds_b64))
    creds = service_account.Credentials.from_service_account_info(
        creds_json, scopes=["https://www.googleapis.com/auth/documents.readonly"]
    )
    return build("docs", "v1", credentials=creds)


def read_google_doc(service, doc_id: str) -> str:
    doc = service.documents().get(documentId=doc_id).execute()
    text = ""
    for element in doc.get("body", {}).get("content", []):
        for para_element in element.get("paragraph", {}).get("elements", []):
            text_run = para_element.get("textRun", {})
            text += text_run.get("content", "")
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    enc = tiktoken.encoding_for_model("gpt-4o")
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        start = end - overlap
    return chunks


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return [d.embedding for d in resp.data]


def main():
    print("Initializing clients...")
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    docs_service = get_docs_service()

    # Create index if it doesn't exist
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=os.environ.get("PINECONE_ENV", "us-east-1")),
        )
    else:
        print(f"Index '{INDEX_NAME}' already exists.")

    index = pc.Index(INDEX_NAME)

    all_vectors = []
    for doc in DOCS:
        print(f"\nProcessing: {doc['name']}...")
        try:
            text = read_google_doc(docs_service, doc["id"])
        except Exception as e:
            print(f"  ERROR reading doc: {e}")
            continue

        print(f"  Read {len(text)} characters")
        chunks = chunk_text(text)
        print(f"  Split into {len(chunks)} chunks")

        embeddings = embed_texts(openai_client, chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vec_id = f"{doc['id']}_chunk_{i}"
            all_vectors.append({
                "id": vec_id,
                "values": embedding,
                "metadata": {
                    "text": chunk,
                    "doc_name": doc["name"],
                    "doc_id": doc["id"],
                    "category": doc["category"],
                    "priority": doc["priority"],
                    "chunk_index": i,
                },
            })

    # Upsert in batches of 100
    print(f"\nUpserting {len(all_vectors)} vectors to Pinecone...")
    batch_size = 100
    for i in range(0, len(all_vectors), batch_size):
        batch = all_vectors[i : i + batch_size]
        index.upsert(vectors=batch)
        print(f"  Upserted batch {i // batch_size + 1}")

    print("\nDone! All docs indexed.")
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")


if __name__ == "__main__":
    main()
