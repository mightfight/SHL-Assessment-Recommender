import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

for m in genai.list_models():
    if 'embed' in m.name.lower():
        print(f"Model: {m.name}, Supported Methods: {m.supported_generation_methods}")
