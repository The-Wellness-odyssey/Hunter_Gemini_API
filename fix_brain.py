import sys
import subprocess

try:
    import google.genai
    print(f"📦 Current Library Version: {google.genai.__version__}")
    
    # The Ghost Test
    if "1.56" in google.genai.__version__:
        print("\n👻 GHOST DETECTED! You are running the wrong library.")
        print("   The system installed 'google-api-core' pretending to be 'google-genai'.")
    elif "0.4" in google.genai.__version__:
        print("\n✅ Version looks correct (0.4.x).")
        # Check for the attribute
        from google import genai
        client = genai.Client(api_key="test")
        if hasattr(client, "file_search_stores"):
             print("   ✨ 'file_search_stores' is AVAILABLE. You are ready.")
        else:
             print("   ⚠️ 'file_search_stores' is MISSING. Weird.")
    else:
        print(f"\n⚠️ Unknown version: {google.genai.__version__}")

except ImportError:
    print("❌ Library not installed.")

print("\n--- THE FIX ---")
print("Run this command in your terminal right now to force the correct version:")
print("pip install google-genai==0.4.1 --force-reinstall")