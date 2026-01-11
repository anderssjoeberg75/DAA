"""
main.py - Central Brain for DAA Digital Advanced Assistant
Project: DAA Digital Advanced Assistant
All code in English.
Features: Async HTTP, Streaming, SQLite Persistence (Memory).
"""
import os
import json
import sqlite3
import uuid
import httpx
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- CONFIGURATION ---
OLLAMA_URL = "http://127.0.0.1:11434"
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
DB_PATH = "/opt/daa/daa_memory.db"

# Global HTTP client
http_client = None

# --- DATABASE LOGIC ---
def init_db():
    """Initializes the SQLite database for chat history."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
              CREATE TABLE IF NOT EXISTS messages (
                                                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                      session_id TEXT NOT NULL,
                                                      role TEXT NOT NULL,
                                                      content TEXT NOT NULL,
                                                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
              )
              ''')
    conn.commit()
    conn.close()

def save_message(session_id, role, content):
    """Saves a single message to the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
              (session_id, role, content))
    conn.commit()
    conn.close()

def get_history(session_id):
    """Retrieves chat history for a specific session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def clear_history(session_id):
    """Deletes history for a session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

# --- LIFECYCLE ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    init_db() # Ensure DB exists on startup
    http_client = httpx.AsyncClient(timeout=120.0)
    print("🚀 DAA Brain: Database & Async Client Initialized")
    yield
    if http_client:
        await http_client.aclose()

app = FastAPI(lifespan=lifespan)

# --- STREAMING GENERATORS WITH SAVING ---
async def stream_wrapper(generator, session_id, user_text):
    """
    Wraps the stream to save the conversation to DB automatically.
    1. Saves User Message immediately.
    2. Accumulates Assistant response chunks.
    3. Saves Assistant Message when stream finishes.
    """
    # Save User Input
    save_message(session_id, "user", user_text)

    full_response = ""
    try:
        async for chunk in generator:
            full_response += chunk
            yield chunk
    finally:
        # Save Assistant Response (even if partial)
        if full_response:
            save_message(session_id, "assistant", full_response)

async def stream_gemini(model_id, messages):
    if not GOOGLE_API_KEY:
        yield "⚠️ Error: Gemini API Key missing."
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent?key={GOOGLE_API_KEY}&alt=sse"

    # Format for Gemini
    contents = []
    for m in messages:
        if m['role'] == 'system': continue
        role = "model" if m['role'] == 'assistant' else "user"
        contents.append({"role": role, "parts": [{"text": m['content']}]})

    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": "You are Nova, an advanced AI assistant. Be helpful, precise, and concise."}]}
    }

    try:
        async with http_client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    try:
                        json_str = line[5:].strip()
                        if not json_str: continue
                        data = json.loads(json_str)
                        if "candidates" in data and data["candidates"]:
                            part = data["candidates"][0]["content"]["parts"][0]
                            if "text" in part:
                                yield part["text"]
                    except Exception:
                        continue
    except Exception as e:
        yield f"\n⚠️ Gemini Error: {str(e)}"

async def stream_ollama(model_id, messages):
    try:
        payload = {"model": model_id, "messages": messages, "stream": True}
        async with http_client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done", False): break
                    except: continue
    except Exception as e:
        yield f"\n⚠️ Ollama Error: {str(e)}"

# --- ENDPOINTS ---

@app.get("/api/models")
async def get_models():
    combined_models = []
    # Gemini
    if GOOGLE_API_KEY and http_client:
        try:
            resp = await http_client.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}", timeout=5.0)
            if resp.status_code == 200:
                for m in resp.json().get('models', []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        mid = m['name'].replace("models/", "")
                        combined_models.append({"id": mid, "name": f"Gemini: {m.get('displayName', mid)}"})
        except: pass
    # Ollama
    try:
        if http_client:
            resp = await http_client.get(f"{OLLAMA_URL}/api/tags", timeout=1.0)
            if resp.status_code == 200:
                for m in resp.json().get('models', []):
                    combined_models.append({"id": m['name'], "name": f"Ollama: {m['name']}"})
    except: pass
    return combined_models

class ChatRequest(BaseModel):
    model: str
    messages: list
    session_id: str

@app.post("/api/chat")
async def chat(req: ChatRequest):
    # Determine generator
    if "gemini" in req.model:
        gen = stream_gemini(req.model, req.messages)
    else:
        gen = stream_ollama(req.model, req.messages)

    # Get last user message for saving
    last_user_msg = req.messages[-1]['content']

    # Wrap with DB saver
    return StreamingResponse(
        stream_wrapper(gen, req.session_id, last_user_msg),
        media_type="text/plain"
    )

@app.get("/api/history/{session_id}")
async def fetch_history(session_id: str):
    return get_history(session_id)

@app.delete("/api/history/{session_id}")
async def delete_history_endpoint(session_id: str):
    clear_history(session_id)
    return {"status": "cleared"}

app.mount("/", StaticFiles(directory="/opt/daa/public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)