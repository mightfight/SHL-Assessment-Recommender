"""
FastAPI Application — SHL Assessment Recommendation API
Endpoints:
  GET  /health    — health check
  POST /recommend — recommendation engine
"""

import os
import sys
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Ensure backend/ is on path for local imports
sys.path.insert(0, os.path.dirname(__file__))

from recommender import recommend
from embeddings import get_collection

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up the vector store — auto-builds embeddings if empty."""
    print("Starting SHL Recommendation API...")
    try:
        col = get_collection()
        count = col.count()
        if count == 0:
            print("  Vector store empty — auto-building embeddings (first run)...")
            from embeddings import build_vector_store
            build_vector_store()
            count = col.count()
        print(f"  ✅ Vector store ready: {count} assessments")
    except Exception as e:
        print(f"  ⚠️  Vector store init error: {e}")
    yield
    print("Shutting down...")


app = FastAPI(
    title="SHL Assessment Recommendation API",
    description="Recommends SHL assessments based on job descriptions or natural language queries.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so frontend can call API from any host
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Models ───────────────────────────────────────────────

class RecommendRequest(BaseModel):
    query: str

    class Config:
        json_schema_extra = {
            "example": {
                "query": "I am hiring Java developers who can collaborate with business teams"
            }
        }


class Assessment(BaseModel):
    url: str
    name: str
    adaptive_support: str
    description: str
    duration: int
    remote_support: str
    test_type: list[str]


class RecommendResponse(BaseModel):
    recommended_assessments: list[Assessment]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Returns API health status."""
    return {"status": "healthy"}


@app.post("/recommend", response_model=RecommendResponse, tags=["Recommendations"])
async def post_recommendations(request: RecommendRequest):
    """
    Given a natural language query, job description text, or JD URL,
    returns 5–10 most relevant SHL Individual Test Solutions.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    return await _handle_recommend(query)


@app.get("/recommend", response_model=RecommendResponse, tags=["Recommendations"])
async def get_recommendations(query: str):
    """
    Support GET requests for convenience/test automation. Query is provided as a
    URL parameter `?query=...`.
    """
    q = query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    return await _handle_recommend(q)


async def _handle_recommend(query: str) -> dict:
    """Shared logic for POST and GET endpoints."""
    try:
        results = recommend(query, num_results=10)
        # Ensure 1-10 results
        results = results[:10]
        if len(results) < 1:
            raise HTTPException(status_code=404, detail="No recommendations found for this query.")
        return {"recommended_assessments": results}
    except HTTPException:
        raise
    except Exception as e:
        print(f"  Error in /recommend: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


# ─── Serve Frontend ───────────────────────────────────────────────────────────

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
