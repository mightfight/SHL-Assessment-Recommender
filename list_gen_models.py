import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(f"Model: {m.name}")
