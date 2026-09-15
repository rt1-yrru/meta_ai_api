
Meta AI Python API (metaai-api)
An unofficial Python API wrapper for Meta AI.
Due to updated browser flags, Cloudflare protection, and bot detection on Meta AI, traditional HTTP request wrappers often fail. This version leverages Playwright under the hood to manage full browser automation while utilizing session cookies (datr & ecto_1_sess) for authenticated interactions.
🚀 Features
Playwright Automation: Reliable DOM interaction handling through headful or headless Chromium instances.
Session Authentication: Pass session cookies (datr, ecto_1_sess) directly to bypass login steps.
Full Response Capture: Directly yields raw string payload objects from Meta AI, bypassing truncated client-side text previews.
Conversation Management: Fetch and list past session history directly from the backend dashboard.
Headless & Headed Modes: Toggle headed=True anytime to visually debug browser execution state.
📦 Prerequisites & Installation
1. Install standard dependencies
Ensure you have Python 3.8+ installed along with playwright:



Bash
pip install playwright


2. Install Playwright Webkit/Chromium Binaries



Bash
playwright install chromium


🔑 Fetching Required Meta.ai Cookies
Before executing scripts, retrieve your session tokens manually from your web browser:
Open your browser and log into https://www.meta.ai.
Open Developer Tools (F12 or Ctrl + Shift + I).
Navigate to the Application tab (or Storage in Firefox) -> Cookies -> [https://www.meta.ai](https://www.meta.ai).
Locate and copy the following two keys:
datr
ecto_1_sess
🧪 Usage & Testing
Create a script (e.g., test_meta.py) and use the snippet below:



Python
from metaai_api import MetaAI

# Initialize client with extracted session cookies
ai = MetaAI(
    cookies={
        "datr": "YOUR_DATR_COOKIE_HERE",
        "ecto_1_sess": "YOUR_ECTO_1_SESS_COOKIE_HERE"
    },
    # headed=True  # Uncomment if you want to visually see the browser running
)

# -------------------------------------------------------------
# 1. Interactive Chat
# -------------------------------------------------------------
query = input("Enter your query/prompt to Meta AI: ")

# Prompt execution
reply = ai.prompt(query)

# NOTE: `reply["message"]` usually truncates part of the response,
# so inspect/carve out the raw data from `reply` directly.
print("\n--- Raw Response ---")
print(reply)


# -------------------------------------------------------------
# 2. List Past Conversations
# -------------------------------------------------------------
# convs = ai.list_conversations()
# print("\n--- Conversation History ---")
# for c in convs:
#     print(c.get("title"))


# -------------------------------------------------------------
# 3. Clean up browser sessions
# -------------------------------------------------------------
ai.close()


⚠️ Key Considerations
Response Truncation (reply["message"]): Meta's UI API splits large payloads into partial string tokens. To read complete output arrays, process the primary returned object reply directly rather than depending exclusively on reply["message"].
Debugging: If queries timeout or stall during execution, set headed=True during initialization to observe Playwright's actual interaction state on the page.
