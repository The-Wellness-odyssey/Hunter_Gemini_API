import os

# 1. Define Categories
PROJECT_MAP = {
    "Diecast": ["hot wheels", "camaro", "ebay", "diecast", "redline"],
    "Fabrication": ["welding", "tig", "mig", "aluminum", "steel", "lathe"],
    "General": [] 
}

print("🧹 Initializing Local Memory Cleaner...")

# 2. Read Raw Logs
try:
    with open("chat_history.txt", "r", encoding="utf-8") as f:
        logs = f.readlines()
except FileNotFoundError:
    print("❌ Error: chat_history.txt not found. Please create it!")
    exit()

# 3. Sort Logs
sorted_memories = {key: [] for key in PROJECT_MAP.keys()}

print(f"   Processing {len(logs)} lines...")
for log in logs:
    log = log.strip()
    if len(log) < 5: continue # Skip junk
    
    target = "General"
    for p, kws in PROJECT_MAP.items():
        if any(k in log.lower() for k in kws):
            target = p
            break
    sorted_memories[target].append(log)

# 4. Save to Memory Bank
# We write ONE file that the App will read directly
with open("memory_bank.txt", "w", encoding="utf-8") as f:
    f.write("# GEMINI BRAIN MEMORY BANK\n\n")
    
    for category, lines in sorted_memories.items():
        if lines:
            f.write(f"## CATEGORY: {category.upper()}\n")
            for line in lines:
                f.write(f"- {line}\n")
            f.write("\n")

print("\n🎉 SUCCESS!")
print("   'memory_bank.txt' has been created.")
print("   Your app will now read this file directly. No API upload needed.")