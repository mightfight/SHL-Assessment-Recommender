"""
Start the SHL Assessment Recommendation API from project root.
Usage: python run.py
"""
import os, sys

# Add backend to path so imports work from root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False,
    )
