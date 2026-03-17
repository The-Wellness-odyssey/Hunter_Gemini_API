import os
from google import genai

# Load your key from the environment or paste it here for a quick test
# (Or better, let's load it from your secrets file so we don't paste it)
import toml
try:
    secrets = toml.load(".streamlit/secrets.toml")
    api_key = secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
    
    print("📋 AVAILABLE MODELS:")
    print("--------------------")
    for m in client.models.list():
        if "generateContent" in m.supported_actions:
            print(f"- {m.name}")
            
except Exception as e:
    print(f"❌ Error: {e}")