"""
RAG Recommendation Pipeline
Retrieves top candidates from ChromaDB → re-ranks using Gemini for balanced results.
"""

import json
import os
import re
import requests as http_requests
from bs4 import BeautifulSoup

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

try:
    from embeddings import search
except ImportError:
    from backend.embeddings import search

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Configure Gemini
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
    _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
else:
    _gemini_model = None


RERANK_PROMPT = """You are an expert HR assessment consultant at SHL.
Given a job description or hiring query and a list of candidate SHL assessments,
your task is to select the MOST RELEVANT assessments for that query.

IMPORTANT RULES:
1. Return between 5 and 10 assessments (prefer 10 if enough good matches exist).
2. If the query involves BOTH technical skills AND soft/behavioral skills, include a BALANCED MIX of:
   - "Knowledge & Skills" (K) type: for technical/functional skills
   - "Personality & Behavior" (P) type: for soft skills, teamwork, leadership
3. If the query is purely technical, prioritize Knowledge & Skills assessments.
4. If the query mentions specific skills (Python, Java, SQL, etc.), prioritize those specific tests.
5. If the query mentions cognitive ability, include Ability & Aptitude (A) tests.
6. Order results from most relevant to least relevant.

QUERY: {query}

CANDIDATE ASSESSMENTS (JSON array):
{candidates}

Respond ONLY with a valid JSON object in this exact format, no explanation:
{{
  "selected_indices": [0, 2, 5, ...]
}}
Where indices refer to the 0-based index in the CANDIDATE ASSESSMENTS list above.
"""


def fetch_url_text(url: str) -> str:
    """Fetch text content from a URL (for JD URL input)."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        resp = http_requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Limit to 3000 chars to avoid token overload
        return text[:3000]
    except Exception as e:
        print(f"  Warning: Could not fetch URL {url}: {e}")
        return url


def is_url(text: str) -> bool:
    """Check if the input is a URL."""
    return bool(re.match(r"https?://", text.strip()))


def rerank_with_gemini(query: str, candidates: list[dict], num_results: int = 10) -> list[dict]:
    """Use Gemini to intelligently re-rank and select top candidates."""
    if not _gemini_model:
        print("  Gemini not configured — using cosine similarity ranking")
        return candidates[:num_results]

    # Prepare compact candidate representation for the prompt
    compact = []
    for i, c in enumerate(candidates):
        compact.append({
            "index": i,
            "name": c["name"],
            "test_type": c["test_type"],
            "description": c["description"][:200],
            "job_levels": c["job_levels"],
            "duration": c["duration"],
            "remote_support": c["remote_support"],
        })

    prompt = RERANK_PROMPT.format(
        query=query,
        candidates=json.dumps(compact, indent=2)
    )

    try:
        response = _gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=512,
            )
        )
        raw = response.text.strip()

        # Extract JSON from response
        json_match = re.search(r'\{.*"selected_indices".*?\}', raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            indices = result.get("selected_indices", [])
            # Validate indices
            indices = [i for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
            selected = [candidates[i] for i in indices[:10]]
            if len(selected) >= 1:
                return selected
    except Exception as e:
        print(f"  Gemini re-ranking failed: {e}. Falling back to similarity ranking.")

    # Fallback: return top by similarity
    return candidates[:num_results]


def recommend(query: str, num_results: int = 10) -> list[dict]:
    """
    Full RAG pipeline:
    1. Resolve URL to text if needed
    2. Semantic search in ChromaDB (top 20 candidates)
    3. Gemini re-ranking for intelligent selection
    """
    # Step 1: Resolve URL input
    effective_query = query.strip()
    if is_url(effective_query):
        print(f"  Detected URL input. Fetching content from: {effective_query}")
        fetched_text = fetch_url_text(effective_query)
        effective_query = fetched_text if fetched_text else effective_query

    # Step 2: Semantic retrieval
    candidates = search(effective_query, top_k=20)
    print(f"  Retrieved {len(candidates)} candidates from vector store")

    # Step 3: LLM re-ranking
    selected = rerank_with_gemini(effective_query, candidates, num_results=num_results)
    print(f"  Final recommendations: {len(selected)}")

    # Step 4: Format output to match API spec
    formatted = []
    for a in selected:
        formatted.append({
            "url": a["url"],
            "name": a["name"],
            "adaptive_support": a.get("adaptive_support", "No"),
            "description": a.get("description", ""),
            "duration": int(a.get("duration") or 0),
            "remote_support": a.get("remote_support", "No"),
            "test_type": a.get("test_type", []),
        })

    return formatted


if __name__ == "__main__":
    # Quick test
    results = recommend("I need to hire Java developers who can collaborate with business teams")
    print(json.dumps(results, indent=2))
