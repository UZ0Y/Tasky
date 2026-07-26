import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Locate root directory and load environment variables
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(dotenv_path=ROOT / ".env")

def test_gemini_api():
    print("----------------------------------------")
    print("🔍 Testing Gemini API Connection...")
    print("----------------------------------------")

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        print("❌ ERROR: GEMINI_API_KEY is missing or not set in the .env file.")
        return

    print(f"🔑 API Key found (starts with: {api_key[:5]}...)")
    print(f"🤖 Using Model: {model_name}")

    try:
        client = genai.Client(api_key=api_key)
        
        print("🚀 Sending test prompt to Gemini...")
        response = client.models.generate_content(
            model=model_name,
            contents="Say hello and confirm you are online and working in one short sentence.",
        )

        if response and response.text:
            print("✅ SUCCESS! Response received from Gemini:")
            print(f"💬 '{response.text.strip()}'")
        else:
            print("⚠️ WARNING: Received empty response from model.")

    except Exception as e:
        print(f"❌ API CONNECTION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_api()