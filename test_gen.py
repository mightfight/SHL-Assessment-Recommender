import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    result = model.generate_content("Hello")
    print("SUCCESS: gemini-1.5-flash")
    print(result.text)
except Exception as e:
    print(f"Error flash: {e}")

try:
    model = genai.GenerativeModel("gemini-1.5-pro")
    result = model.generate_content("Hello")
    print("SUCCESS: gemini-1.5-pro")
    print(result.text)
except Exception as e:
    print(f"Error pro: {e}")
