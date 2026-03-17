import google.genai
print(f"✅ Library Version: {google.genai.__version__}")

try:
    from google import genai
    client = genai.Client(api_key="TEST") # Fake key just to check attributes
    
    if hasattr(client, "corpora"):
        print("✅ SUCCESS: 'client.corpora' exists! You are ready.")
    else:
        print("❌ FAILURE: 'client.corpora' is MISSING.")
        print("   Current Client attributes:", dir(client))
except Exception as e:
    print(f"❌ Error during check: {e}")