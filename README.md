# SHL Assessment Recommendation System

An AI-powered RAG system that recommends SHL assessments from natural language queries or job descriptions.

## Project Structure
```
shl-assessment-recommender/
├── backend/
│   ├── scraper.py          # Crawl SHL catalog (377+ assessments)
│   ├── embeddings.py       # sentence-transformers + ChromaDB
│   ├── recommender.py      # RAG pipeline + Gemini re-ranking
│   ├── app.py              # FastAPI server
│   └── data/               # assessments.json + chroma_db/
├── evaluation/
│   ├── evaluate.py         # Mean Recall@10 on train set
│   └── generate_predictions.py  # predictions.csv for test set
├── frontend/               # Vanilla HTML/CSS/JS web UI
├── Gen_AI Dataset.xlsx     # Train + test queries
├── .env                    # Set GEMINI_API_KEY here
└── requirements.txt
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Gemini API key
Edit `.env`:
```
GEMINI_API_KEY=your_key_here
```
Get a free key at https://aistudio.google.com

### 3. Scrape the SHL catalog
```bash
python backend/scraper.py
```
This creates `backend/data/assessments.json` (377+ items). Takes ~10-15 min.

### 4. Build the vector store
```bash
python backend/embeddings.py
```
Generates embeddings and stores in ChromaDB.

### 5. Run the API server
```bash
python backend/app.py
```
API runs at http://localhost:8000

### 6. Open the frontend
Visit http://localhost:8000 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/recommend` | POST, GET | Get 5–10 assessment recommendations (GET uses `?query=`)

### POST /recommend
```json
// Request
{"query": "Java developer who collaborates with business teams"}

// Response
{
  "recommended_assessments": [
    {
      "url": "https://www.shl.com/solutions/products/product-catalog/view/...",
      "name": "Java (New)",
      "adaptive_support": "No",
      "description": "...",
      "duration": 30,
      "remote_support": "Yes",
      "test_type": ["Knowledge & Skills"]
    }
  ]
}
```

## Evaluation
```bash
python evaluation/evaluate.py         # Mean Recall@10 on train set
python evaluation/generate_predictions.py  # predictions.csv for submission
```

## Deployment Notes

The application can be deployed to any Python-capable host. Two common free-tier
options are **Render** and **Heroku**. To avoid build/runtime errors, especially
on Render which currently uses Python 3.14 by default, take the following steps:

1. **Pin Python version**
   * Add a `runtime.txt` with `python-3.12.2` or set the environment variable
     `PYTHON_VERSION=3.12.2` on Render.
   * This prevents issues compiling newer packages such as `pydantic-core`.

2. **Upgrade build tools**
   * Use a build command like:
     ```bash
     pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
     ```
   * This ensures wheels are built correctly.

3. **ChromaDB/Pydantic fix**
   * The requirements already pin `chromadb>=0.5.5` and `pydantic>=1.10,<2.1` to
     avoid the type-inference bug.
   * On Render, add an environment variable:
     `CHROMA_SERVER_NOFILE=65535` (or any integer) to bypass Pydantic inference.

4. **Environment variables**
   * `GEMINI_API_KEY` (required)
   * `CHROMA_TELEMETRY_OFF=True` (optional)
   * `CHROMA_SERVER_NOFILE` (see above)
   * `PYTHON_VERSION`/`runtime.txt` as noted.

Once deployed, verify the health check and `/recommend` endpoints work at the
public URL, and the front-end should be accessible at the root path.
