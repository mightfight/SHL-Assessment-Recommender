"""
Embeddings + ChromaDB Vector Store
Uses Google Gemini Embedding API — no PyTorch required.
"""

import os
os.environ['CHROMA_TELEMETRY_OFF'] = 'True'

import json
import time
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

BASE_DIR = os.path.dirname(__file__)
ASSESSMENTS_FILE = os.path.join(BASE_DIR, "data", "assessments.json")
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma_db")
COLLECTION_NAME = "shl_assessments"
EMBED_MODEL = "models/gemini-embedding-001"  # Gemini free embedding model

_collection = None


from chromadb.config import Settings

def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using Gemini embedding API, with batching + rate limiting."""
    embeddings = []
    BATCH = 15  # Gemini API handles up to 100 but keeping it small
    for i in range(0, len(texts), BATCH):
        batch = texts[i: i + BATCH]
        try:
            result = genai.embed_content(
                model=EMBED_MODEL,
                content=batch,
                task_type="retrieval_document",
            )
            embeddings.extend(result["embedding"])
        except Exception as e:
            print(f"  Rate limit hit at batch {i}: wait 60 seconds... ({str(e)[:50]})")
            time.sleep(65)
            result = genai.embed_content(
                model=EMBED_MODEL,
                content=batch,
                task_type="retrieval_document",
            )
            embeddings.extend(result["embedding"])
        time.sleep(4)  # 15 RPM average limit
    return embeddings


def make_rich_text(a: dict) -> str:
    """Build rich combined text for embedding."""
    parts = [
        a.get("name", ""),
        a.get("description", ""),
        "Test Type: " + ", ".join(a.get("test_type", [])) if a.get("test_type") else "",
        "Job Levels: " + ", ".join(a.get("job_levels", [])) if a.get("job_levels") else "",
        f"Duration: {a['duration']} minutes" if a.get("duration") else "",
        f"Remote: {a.get('remote_support', 'No')}",
        f"Adaptive: {a.get('adaptive_support', 'No')}",
    ]
    return ". ".join(p for p in parts if p)


def build_vector_store():
    """One-time: embed all assessments and persist in ChromaDB."""
    print("Loading assessments from JSON...")
    with open(ASSESSMENTS_FILE, encoding="utf-8") as f:
        assessments = json.load(f)
    print(f"  Loaded {len(assessments)} assessments")

    collection = get_collection()

    # Clear and rebuild
    existing = collection.count()
    if existing > 0:
        print(f"  Clearing existing {existing} embeddings...")
        ids = collection.get()["ids"]
        if ids:
            collection.delete(ids=ids)

    texts = [make_rich_text(a) for a in assessments]
    ids = [f"a_{i}" for i in range(len(assessments))]
    metadatas = []
    for a in assessments:
        metadatas.append({
            "name": a.get("name", ""),
            "url": a.get("url", ""),
            "description": (a.get("description", "") or "")[:500],
            "test_type": "|".join(a.get("test_type", [])),
            "job_levels": "|".join(a.get("job_levels", [])),
            "duration": int(a.get("duration") or 0),
            "remote_support": a.get("remote_support", "No"),
            "adaptive_support": a.get("adaptive_support", "No"),
        })

    print(f"  Generating Gemini embeddings for {len(texts)} assessments...")
    embeddings = embed_texts(texts)

    print("  Inserting into ChromaDB...")
    BATCH = 100
    for i in range(0, len(assessments), BATCH):
        collection.add(
            ids=ids[i: i + BATCH],
            embeddings=embeddings[i: i + BATCH],
            documents=texts[i: i + BATCH],
            metadatas=metadatas[i: i + BATCH],
        )

    print(f"  ✅ Vector store ready: {collection.count()} items")


def search(query: str, top_k: int = 20) -> list[dict]:
    """Query vector store using Gemini embedding for the query."""
    collection = get_collection()

    result = genai.embed_content(
        model=EMBED_MODEL,
        content=query,
        task_type="retrieval_query",
    )
    query_embedding = result["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["metadatas", "distances"],
    )

    out = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        out.append({
            "name": meta.get("name", ""),
            "url": meta.get("url", ""),
            "description": meta.get("description", ""),
            "test_type": [t for t in meta.get("test_type", "").split("|") if t],
            "job_levels": [j for j in meta.get("job_levels", "").split("|") if j],
            "duration": meta.get("duration", 0),
            "remote_support": meta.get("remote_support", "No"),
            "adaptive_support": meta.get("adaptive_support", "No"),
            "similarity": float(1 - results["distances"][0][i]),
        })
    return out


if __name__ == "__main__":
    build_vector_store()
