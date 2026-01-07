"""
main.py - Central Brain
-----------------------
Orchestrates AI logic and delegates tasks to tools or remote agents.
"""
import os
import re
import json
import requests
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# Import our new calendar tools
from tools.google_calendar import create_calendar_event, calendar_tool_definition

# --- CONFIGURATION ---
OLLAMA_URL = "http://ollama.andrix.local:11434"
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
PC_CLIENT_IP = "192.168.1.XX" # Your local Windows PC IP

app = FastAPI()

SERVER_NAME = "Nova AI"
SERVER_PERSONA = "You are a helpful AI."

def load_config():
    global SERVER_NAME, SERVER_PERSONA
    if os.path.exists("persona.js"):
        with open("persona.js", "r", encoding="utf-8") as f:
            content = f.read()
            p_match = re.search(r'`([\s\S]*)`', content)
            n_match = re.search(r'const ASSISTANT_NAME = ["\'](.*?)["\'];', content)
            if p_match: SERVER_PERSONA = p_match.group(1).strip()
            if n_match: SERVER_NAME = n_match.group(1).strip()

load_config()

def delegate_to_pc(action, target):
    """Sends command to the remote PC_agent.py."""
    try:
        resp = requests.post(f"http://{PC_CLIENT_IP}:5001/execute",
                             json={"action": action, "target": target}, timeout=5)
        return resp.json()
    except:
        return {"status": "error", "message": "PC Agent offline"}

@app.get("/api/config")
async def get_config():
    return {"name": SERVER_NAME}

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    model = data.get("model")
    messages = data.get("messages")

    if "gemini" in model:
        # Combine all tools for Gemini
        tools = [{
            "function_declarations": [
                calendar_tool_definition,
                {
                    "name": "open_local_app",
                    "description": "Open a program on the user's PC",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {"app_name": {"type": "STRING"}},
                        "required": ["app_name"]
                    }
                }
            ]
        }]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}"
        contents = [{"role": "model" if m['role'] == 'assistant' else "user",
                     "parts": [{"text": m['content']}]} for m in messages if m['role'] != 'system']

        # Inject dynamic time context
        system_context = f"{SERVER_PERSONA}\n\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        payload = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": system_context}]},
            "tools": tools
        }

        response = requests.post(url, json=payload).json()
        part = response['candidates'][0]['content']['parts'][0]

        if 'functionCall' in part:
            call = part['functionCall']
            name = call['name']
            args = call['args']

            if name == "create_calendar_event":
                res = create_calendar_event(args)
                return {"message": {"content": f"📅 **Calendar:** Event created!\n[Link]({res.get('link')})"}}

            if name == "open_local_app":
                res = delegate_to_pc("open_app", args['app_name'])
                return {"message": {"content": f"🚀 **PC Agent:** Opening `{args['app_name']}`. Status: {res.get('status')}"}}

        return {"message": {"content": part.get('text', 'No response')}}

    # Ollama integration
    res = requests.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": messages, "stream": False})
    return res.json()

app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)