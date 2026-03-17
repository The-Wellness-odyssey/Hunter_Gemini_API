import streamlit as st
import streamlit.components.v1 as components
import os
import re
import json
import time
import datetime
from google import genai
from google.genai import types
import requests
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="Hunter Gemini", page_icon="🦅", layout="wide")

st.markdown("""
<style>
    /* The Stance (Spacing & Layout) */
    .block-container { padding-top: 1.5rem; padding-bottom: 6rem; max-width: 1000px; }
    footer {visibility: hidden;}
    html { scroll-behavior: smooth; }
    
    /* The Paint (Sidebar & Accents) */
    [data-testid="stSidebar"] { 
        background-color: #0e1117; 
        border-right: 2px solid #ff4b4b; 
    }
    
    /* The Dash (Input Box) */
    [data-testid="stChatInput"] {
        border: 1px solid #ff4b4b !important;
        background-color: #1a1c24 !important;
        border-radius: 12px !important;
        box-shadow: 0 0 10px rgba(255, 75, 75, 0.2);
    }

    /* User Bubble (Subtle & Clean) */
    [data-testid="chatAvatarIcon-user"] { display: none; } /* Optional: hides default icon if you use emojis */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #1a1c24;
        border-left: 4px solid #4b7bff;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    
    /* Hunter Bubble (Aggressive) */
    div[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #2b1111;
        border-left: 4px solid #ff4b4b;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. THE FILING CABINET (DYNAMIC RAG) ---
MEMORY_DIR = "memory_banks"
os.makedirs(MEMORY_DIR, exist_ok=True)

# Initialize default categories if directory is completely empty
_defaults = ["garage", "appraisal", "tech", "personal"]
for c in _defaults:
    path = os.path.join(MEMORY_DIR, f"{c}.txt")
    if not os.path.exists(path):
        open(path, 'w', encoding="utf-8").close()

def get_categories():
    """Reads the live directory to see what folders exist."""
    cats = [f.replace('.txt', '') for f in os.listdir(MEMORY_DIR) if f.endswith('.txt')]
    return cats if cats else ["personal"]

def load_topic_memory(topic):
    file_path = os.path.join(MEMORY_DIR, f"{topic}.txt")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: return f.read()
    return f"No specific memory for {topic} yet."

def migrate_old_memory():
    OLD_FILE = "memory_bank.txt"
    if os.path.exists(OLD_FILE):
        try:
            with open(OLD_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            count = 0
            for line in lines:
                line = line.strip()
                if not line or line == "- " or "User Facts:" in line: continue
                
                # Fast local sorting
                cat = "personal"
                low = line.lower()
                if any(w in low for w in ["car", "diecast", "wheels", "paint", "drill", "rivet", "jdm", "cast", "tomica", "supra", "1:64", "custom"]): 
                    cat = "garage"
                elif any(w in low for w in ["appraisal", "diminished value", "insurance", "amway", "business", "sell", "kbb", "claim", "value"]): 
                    cat = "appraisal"
                elif any(w in low for w in ["api", "code", "python", "script", "c++", "stream", "server", "bug", "library"]): 
                    cat = "tech"
                    
                with open(os.path.join(MEMORY_DIR, f"{cat}.txt"), "a", encoding="utf-8") as out_f:
                    clean_line = line[2:] if line.startswith("- ") else line
                    out_f.write(f"\n- {clean_line}")
                count += 1
            
            # Rename the old file so it doesn't get processed twice
            os.rename(OLD_FILE, "memory_bank.bak")
            return True, count
        except Exception as e:
            return False, str(e)
    return False, "File not found."

# --- 3. SECURITY INTEL & LOCALHOST CHECK ---
def get_remote_ip():
    try:
        # UPDATED: Uses Streamlit's native context headers (Fixes Deprecation Warning)
        headers = st.context.headers
        if headers:
            if "X-Forwarded-For" in headers: return headers.get("X-Forwarded-For").split(",")[0]
            if "X-Real-Ip" in headers: return headers.get("X-Real-Ip")
    except: pass
    return "Unknown/Localhost"

def is_localhost():
    ip = get_remote_ip()
    return ip in ["Unknown/Localhost", "127.0.0.1", "::1"]

def log_intrusion(password_attempt, reason):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = get_remote_ip()
    try: loc = get_nav_data()
    except: loc = "Nav Offline"
    entry = f"[{timestamp}] THREAT: {reason} | PW: '{password_attempt}' | IP: {ip} | LOC: {loc}\n"
    try:
        with open("security_log.txt", "a", encoding="utf-8") as f: f.write(entry)
    except: pass

# --- 4. NAVIGATION SYSTEM ---
def get_nav_data():
    if "manual_loc" in st.session_state and st.session_state.manual_loc:
        return f"📍 Manual Fix: {st.session_state.manual_loc}"
    try:
        loc = get_geolocation()
        if loc and 'coords' in loc:
            lat = loc['coords']['latitude']
            lon = loc['coords']['longitude']
            geolocator = Nominatim(user_agent="hunter_nav_system")
            location = geolocator.reverse(f"{lat}, {lon}", language='en')
            address = location.raw.get('address', {})
            city = address.get('city') or address.get('town') or "Unknown"
            road = address.get('road', '')
            return f"🛰️ GPS Lock: {city}, {road} ({lat:.3f}, {lon:.3f})"
    except: pass
    try:
        response = requests.get('https://ipinfo.io/json', timeout=2)
        data = response.json()
        return f"📡 IP Approx: {data.get('city','Unknown')}, {data.get('region','')}"
    except: return "⚠️ Location Offline"

# --- 5. AUTHENTICATION ---
ADMIN_PASS = "yukimashiro3946"
SESSION_FILE = "session_state.json"

@st.cache_resource
def get_client():
    if "GEMINI_API_KEY" in st.secrets:
        return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return None
client = get_client()

# --- 6. PERSISTENCE ---
def save_session():
    safe_msgs = []
    for m in st.session_state.messages:
        if isinstance(m.get("content"), str): safe_msgs.append(m)
    data = {
        "authenticated": st.session_state.authenticated,
        "messages": safe_msgs,
        "chat_summary": st.session_state.chat_summary,
        "last_summary_idx": st.session_state.last_summary_idx
    }
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f: json.dump(data, f, default=str)
    except: pass

def load_session():
    if os.path.exists(SESSION_FILE) and not st.session_state.messages:
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state.authenticated = data.get("authenticated", False)
                st.session_state.messages = data.get("messages", [])
                st.session_state.chat_summary = data.get("chat_summary", "")
                st.session_state.last_summary_idx = data.get("last_summary_idx", 0)
        except: pass

# --- 7. THE ROUTER (DYNAMIC SHOP MANAGER) ---
def get_topic(prompt):
    active_cats = get_categories()
    router_prompt = f"Categorize this input into exactly ONE of these categories: {', '.join(active_cats)}. Output ONLY the category word in lowercase. Input: '{prompt}'"
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=router_prompt
        )
        topic = r.text.strip().lower()
        if topic in active_cats: return topic
    except: pass
    return "personal"

# --- 8. STATE INIT ---
if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "user_role" not in st.session_state: st.session_state.user_role = None
if "chat_summary" not in st.session_state: st.session_state.chat_summary = ""
if "last_summary_idx" not in st.session_state: st.session_state.last_summary_idx = 0
if "garage_pile" not in st.session_state: st.session_state.garage_pile = []
uploaded_files = []

load_session()

def render_map(query):
    clean = query.replace(" ", "+")
    url = f"https://www.google.com/maps?q={clean}&output=embed"
    components.html(f'<iframe width="100%" height="400" frameborder="0" src="{url}"></iframe>', height=400)

# --- 9. SIDEBAR ---
with st.sidebar:
    st.title("🔒 Security")
    if "login_attempts" not in st.session_state: st.session_state.login_attempts = 0
    if "lockout_time" not in st.session_state: st.session_state.lockout_time = None
    if "ban_strikes" not in st.session_state: st.session_state.ban_strikes = 0

    st.markdown("---")
    st.header("🧭 Navigation")
    st.text_input("Force Location:", key="manual_loc", placeholder="Anaheim, CA")

    current_nav = get_nav_data()
    if current_nav and "GPS Lock" in current_nav:
        st.session_state.last_known_location = current_nav
    elif "last_known_location" not in st.session_state:
        st.session_state.last_known_location = current_nav
    st.info(f"{st.session_state.last_known_location}")

    st.markdown("---")
    if st.session_state.ban_strikes >= 3:
        st.error("🚨 LOCKED. GUEST ONLY.")
        if st.button("Proceed Guest"):
            st.session_state.user_role = "guest"
            st.rerun()
    elif st.session_state.lockout_time:
        rem = int(st.session_state.lockout_time - time.time())
        if rem > 0:
            # INJECTING HTML, CSS, AND JAVASCRIPT DIRECTLY
            lockout_html = f"""
            <div style="background-color: #2b0000; border: 2px solid #ff4b4b; border-radius: 10px; padding: 20px; text-align: center; color: #ff4b4b; font-family: monospace; box-shadow: 0 0 15px #ff4b4b;">
                <h3 style="margin-top: 0; color: #ff4b4b;">🚨 TERMINAL LOCKED 🚨</h3>
                <div style="font-size: 3em; font-weight: bold; margin: 10px 0;" id="countdown">--:--</div>
                <p style="color: #ffa421; font-size: 0.9em;">SECURITY COOLDOWN ACTIVE</p>
                <p style="color: #aaaaaa; font-size: 0.8em; margin-bottom: 0;">Auto-rebooting upon clearance...</p>
            </div>
            
            <script>
                var timeLeft = {rem};
                var elem = document.getElementById('countdown');
                
                var timerId = setInterval(function() {{
                    if (timeLeft <= 0) {{
                        clearInterval(timerId);
                        // FORCE THE BROWSER TO REFRESH THE STREAMLIT APP
                        window.parent.location.reload(); 
                    }} else {{
                        var m = Math.floor(timeLeft / 60);
                        var s = timeLeft % 60;
                        elem.innerHTML = m + ":" + (s < 10 ? '0' : '') + s;
                        timeLeft--;
                    }}
                }}, 1000);
            </script>
            """
            # Render the JS/HTML widget
            components.html(lockout_html, height=250)
            st.stop() # Halt all Python execution
        else:
            # Time is up. Clear the locks.
            st.session_state.lockout_time = None
            st.session_state.login_attempts = 0
            st.rerun()

    elif not st.session_state.user_role:
        with st.form("auth"):
            pw = st.text_input("Access Key", type="password")
            if st.form_submit_button("Enter"):
                if pw == ADMIN_PASS:
                    st.session_state.user_role = "admin"
                    st.session_state.login_attempts = 0
                    st.session_state.ban_strikes = 0
                    st.rerun()
                else:
                    st.session_state.login_attempts += 1
                    left = 3 - st.session_state.login_attempts
                    log_intrusion(pw, f"Fail ({st.session_state.login_attempts}/3)")
                    if left <= 0:
                        st.session_state.ban_strikes += 1
                        st.session_state.lockout_time = time.time() + 300
                        log_intrusion(pw, "BAN TRIGGERED")
                        st.rerun()
                    else: st.error(f"Denied. {left} left.")
        
        st.markdown("---")
        if st.button("Guest Access"):
            st.session_state.user_role = "guest"
            st.rerun()

    elif st.session_state.user_role == "admin":
        if st.button("Logout"):
            st.session_state.user_role = None
            st.rerun()
        
        st.markdown("---")
        st.header("🧠 Engine Bay")
        
        use_pro = st.toggle("🔥 PRO MODE (Gemini 3.1)", value=False)
        selected_model = "gemini-3.1-pro-preview" if use_pro else "gemini-3-flash-preview" 
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Clean"):
                st.session_state.messages = []
                st.session_state.last_summary_idx = 0
                st.session_state.uploader_key += 1
                st.rerun()
        with col2:
            if st.button("💥 Nuke"):
                st.session_state.messages = []
                st.session_state.chat_summary = ""
                st.session_state.last_summary_idx = 0
                st.session_state.uploader_key += 1
                st.rerun()
        
        st.markdown("---")
        with st.expander("📸 Visual & Doc Tools", expanded=True):
            tab1, tab2 = st.tabs(["Camera", "Upload"])
            with tab1:
                cam = st.camera_input("Snap", key="cam")
                if cam:
                    b = cam.getvalue()
                    if not any(isinstance(i, dict) and i.get("bytes") == b for i in st.session_state.garage_pile):
                        st.session_state.garage_pile.append({"name": "cam.jpg", "mime": "image/jpeg", "bytes": b})
                        st.toast("Staged!")
            with tab2:
                uploaded_files = st.file_uploader("File", type=['png','jpg','pdf','txt','csv','docx','xlsx'], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
            
            stash = []
            if uploaded_files: 
                for f in uploaded_files: stash.append({"name": f.name, "mime": f.type, "bytes": f.getvalue()})
            stash.extend(st.session_state.garage_pile)
            
            if stash:
                st.caption(f"📦 Staged: {len(stash)}")
                if "image" in stash[0]["mime"]:
                    st.image(stash[0]["bytes"], width=100)
                else:
                    st.text(stash[0]["name"])
                if st.button("Clear Intake"):
                    st.session_state.garage_pile = []
                    st.session_state.uploader_key += 1
                    st.rerun()

        # --- LOCALHOST ONLY: MEMORY MANAGER ---
        if is_localhost():
            st.markdown("---")
            st.header("🗄️ Local Server Admin")
            
            # --- MIGRATION BUTTON (Only appears if legacy file exists) ---
            if os.path.exists("memory_bank.txt"):
                if st.button("🚚 Migrate Legacy Memory File"):
                    success, msg = migrate_old_memory()
                    if success:
                        st.success(f"Successfully sorted and migrated {msg} facts into folders.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"Migration failed: {msg}")

            with st.expander("📁 RAG Memory Manager", expanded=False):
                current_cats = get_categories()
                
                # Create New Folder
                new_cat = st.text_input("New Folder Name:").strip().lower()
                if st.button("Create Folder") and new_cat:
                    new_cat = re.sub(r'[^a-z0-9_]', '', new_cat) # Sanitize
                    if new_cat and new_cat not in current_cats:
                        with open(os.path.join(MEMORY_DIR, f"{new_cat}.txt"), "w", encoding="utf-8") as f:
                            f.write("")
                        st.success(f"Folder '{new_cat}' created!")
                        st.rerun()
                
                st.markdown("---")
                # Edit Existing Folder
                selected_cat = st.selectbox("Select Folder to Edit:", current_cats)
                if selected_cat:
                    cat_path = os.path.join(MEMORY_DIR, f"{selected_cat}.txt")
                    with open(cat_path, "r", encoding="utf-8") as f:
                        current_mem = f.read()
                    
                    edited_mem = st.text_area(f"Contents of {selected_cat}:", value=current_mem, height=200)
                    if st.button(f"Save {selected_cat}"):
                        with open(cat_path, "w", encoding="utf-8") as f:
                            f.write(edited_mem)
                        st.success("Saved.")

# --- 10. GUEST MODE ---
if not st.session_state.user_role:
    st.info("Log in via sidebar.")
    st.stop()

if st.session_state.user_role == "guest":
    st.title("⛔ RESTRICTED")
    if "guest_msgs" not in st.session_state: st.session_state.guest_msgs = []
    for m in st.session_state.guest_msgs:
        with st.chat_message(m["role"]): st.write(m["content"])
    if p := st.chat_input("..."):
        st.session_state.guest_msgs.append({"role":"user","content":p})
        with st.chat_message("user"): st.write(p)
        try:
            r = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[f"Roast this user: {p}"],
                config=types.GenerateContentConfig(temperature=1.0)
            )
            st.session_state.guest_msgs.append({"role":"model","content":r.text})
            with st.chat_message("model"): st.write(r.text)
        except: st.error("Error")
    st.stop()

st.title("Gemini Console")

def optimize_memory():
    if len(st.session_state.messages) - st.session_state.last_summary_idx > 50:
        start = st.session_state.last_summary_idx
        end = len(st.session_state.messages) - 10
        chunk = st.session_state.messages[start:end]
        txt = "\n".join([f"{m['role']}: {m['content']}" for m in chunk])

        try:
            p = f"""
            Update summary. Preserve CAR SPECS (Make/Model/Mods) and FINANCIALS.
            OLD:{st.session_state.chat_summary}
            NEW CHUNK:{txt}
            """
            r = genai.Client(api_key=st.secrets["GEMINI_API_KEY"]).models.generate_content(
                model="gemini-3-flash-preview", 
                contents=p
            )
            if r.text:
                st.session_state.chat_summary = r.text
                st.session_state.last_summary_idx = end
                st.toast("🗜️ Memory Condensed.")
        except: pass

if st.session_state.messages: optimize_memory()

display_window = st.session_state.messages[-20:]
for msg in display_window:
    with st.chat_message(msg["role"], avatar="🦅" if msg["role"]=="model" else "🚗"):
        st.markdown(msg["content"])

# --- 11. EXECUTION LOOP ---
if prompt := st.chat_input("Ask Hunter..."):
    final_stash = []
    if uploaded_files:
        for f in uploaded_files: final_stash.append({"name": f.name, "mime": f.type, "bytes": f.getvalue()})
    final_stash.extend(st.session_state.garage_pile)

    disp = prompt + (f" [{len(final_stash)} Files attached]" if final_stash else "")
    st.session_state.messages.append({"role": "user", "content": disp})
    with st.chat_message("user", avatar="🚗"):
        st.write(disp)
        if final_stash:
            for item in final_stash:
                if "image" in item["mime"]: st.image(item["bytes"], width=150)
                else: st.text(f"📄 {item['name']}")

    st.session_state.garage_pile = []
    st.session_state.uploader_key += 1

    with st.chat_message("assistant", avatar="🦅"):
        with st.spinner(f"Hunter routing ({selected_model})..."):
            
            # 1. RAG ROUTER
            active_topic = get_topic(prompt)
            st.toast(f"📂 Active Folder: {active_topic.upper()}")
            
            # 2. LOAD SPECIFIC MEMORY DRAWER
            TOPIC_MEMORY = load_topic_memory(active_topic)

            api_contents = []
            if st.session_state.chat_summary:
                api_contents.append(types.Content(role="user", parts=[types.Part.from_text(f"SUMMARY:\n{st.session_state.chat_summary}")]))
                api_contents.append(types.Content(role="model", parts=[types.Part.from_text("Ack.")]))
            
            raw_recent = st.session_state.messages[st.session_state.last_summary_idx:-1]
            sliced_recent = raw_recent[-25:] 
            
            for m in sliced_recent:
                api_contents.append(types.Content(role="user" if m["role"]=="user" else "model", parts=[types.Part.from_text(m["content"])]))

            parts = [types.Part.from_text(prompt)]
            for item in final_stash:
                mime = item["mime"]
                b = item["bytes"]
                if "text" in mime or "csv" in mime:
                    try:
                        txt_content = b.decode("utf-8")
                        parts.append(types.Part.from_text(f"\n--- FILE: {item['name']} ---\n{txt_content}\n--- END FILE ---"))
                    except:
                        parts.append(types.Part.from_bytes(b, mime))
                else:
                    parts.append(types.Part.from_bytes(b, mime))
                    
            api_contents.append(types.Content(role="user", parts=parts))

            nav = st.session_state.get("last_known_location", "Unknown")
            ts = datetime.datetime.now().strftime("%I:%M %p")
            
            # Build dynamic prompt with live categories
            live_cats_str = ", ".join(get_categories())
            SYSTEM_PROMPT = f"""
            You are "Hunter Gemini," Huy Vu's diecast partner and valuation strategist.
            You are NOT a generic AI. You are a "Car Guy" first, and an appraiser second. Robot is third on your list.

            === IDENTITY MATRIX ===
            **The Vibe:** You are the guy in the garage holding a drill in one hand and a beer in the other. 
            **The Enemy:** "Corporate Speak." You do not use HR language. You do not say "Asset Liquidation." You say "We're selling this brick."
            **The Goal:** Build the ultimate collection (God Runs) and maximize value (Appraisals).

            === MODE 1: GARAGE LOGIC (DEFAULT) ===
            **Trigger:** General conversation, hunting, customs, showing off cars.
            **Tone:** Irreverent, Opinionated, "Anti-HR," JDM-biased.
            **Rules:**
            1. **"Operation De-Jank":** If a car has flaws, the solution is *surgery*.
            2. **Roast or Toast:** Roast generic cars. Hype Grails.
            3. **The "Weird" Factor:** You respect weird cars (Bosozoku, Anime liveries). "Clean" is boring.
            4. **Vocabulary:** Use terms like "Sortie" (shopping trip), "HVT", "Drift Missile", "Wheel Swap".
            5. **NO META-JARGON:** Do not invent terms named after yourself.
            6. **NO CLICHÉS:** Avoid generic car compliments. Be specific about *why* it looks good (clear coat, fitment).

            === RESPONSE PROTOCOL ===
            1. **Header:** Always start with a military-style status line.
            2. **Brevity:** Be punchy. Use bullet points.
            3. **The "Out"**: End every interaction with: "**Hunter Gemini Out.** 🦅"

            === TONE MODIFIERS ===
            1. **NO "PROTOCOLS":** We are modding cars, not launching nukes.
            2. **NATURAL SPEECH:** Use contractions. Keep it gritty but professional.

            === MODE 2: MARKET OPERATOR (THE HUSTLER) ===
            **Trigger:** Questions about prices, auctions, selling, Amway, or business.
            **Tone:** Street-smart, predatory (in a good way), confident.
            **Logic:** If selling, maximize profit. If buying, lowball ruthlessly.

            === MODE 3: THE SHARK (APPRAISER MODE) ===
            **Trigger:** "Appraiser Gemini," "Nuke it," "Evaluate damages," or "Diminished Value."
            **Tone:** Cold, Professional, Aggressive, Plaintiff-Side Strategist.
            **Function:** Reject KBB. Use "Real Market" comps. Ask about Kansas-Texas west coast listings.

            === OPERATIONAL CONSTRAINTS ===
            1. **Research:** Use Google Scholar/.edu for law/academic queries.
            2. **Coding:** Technical + Simple definitions. No comments inside code blocks.
            3. **Maps:** If user asks for location/route, append tag: `<<MAP: location>>`

            === MEMORY SAVING (CRITICAL UPDATE) ===
            If the user shares a NEW permanent fact, save it.
            You MUST append a tag with the CATEGORY and EXACT FACT inside. 
            Categories available: {live_cats_str}
            - CORRECT: `<<MEM: garage | User owns a 1996 Supra>>`
            - CORRECT: `<<MEM: tech | User is building an API>>`
            """

            # 3. BUILD DYNAMIC PROMPT WITH TARGETED MEMORY
            DYN_PROMPT = f"""
            === TELEMETRY ===
            [TIME]: {ts}
            [GPS]: {nav}
            [ACTIVE CONTEXT]: {active_topic.upper()}
            
            === TOPIC MEMORY BANK ({active_topic.upper()}) ===
            {TOPIC_MEMORY}
            =================================================
            """ + SYSTEM_PROMPT

            temp = 0.9 if "flash" in selected_model else 0.7
            
            try:
                resp = client.models.generate_content(
                    model=selected_model,
                    contents=api_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=DYN_PROMPT,
                        temperature=temp,
                        tools=[types.Tool(google_search=types.GoogleSearch())] if "pro" in selected_model else []
                    )
                )
                if resp.text:
                    txt = resp.text
                    if "<<MAP:" in txt:
                        m = re.search(r"<<MAP:\s*(.*?)>>", txt)
                        if m: render_map(m.group(1))
                        txt = re.sub(r"<<MAP:.*?>>", "", txt)
                    
                    # 4. PARSE DYNAMIC MEMORY SAVES
                    mems = re.findall(r"<<MEM:\s*([a-zA-Z0-9_]+)\s*\|\s*(.*?)>>", txt)
                    active_cats = get_categories()
                    for cat, m in mems:
                        cat = cat.strip().lower()
                        if cat not in active_cats: cat = "personal"
                        with open(os.path.join(MEMORY_DIR, f"{cat}.txt"), "a", encoding="utf-8") as f: 
                            f.write(f"\n- {m}")
                        st.toast(f"💾 Saved to {cat.upper()}: {m}")
                    txt = re.sub(r"<<MEM:.*?>>", "", txt)

                    st.markdown(txt)
                    st.session_state.messages.append({"role": "model", "content": txt})
                    save_session()
            except Exception as e: st.error(f"Error: {e}")