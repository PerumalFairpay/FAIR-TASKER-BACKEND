import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    genai.configure(api_key=api_key)
    
    print("Available Gemini Models:")
    print("-" * 30)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Name: {m.name}")
                print(f"Display Name: {m.display_name}")
                print(f"Description: {m.description}")
                print("-" * 30)
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
