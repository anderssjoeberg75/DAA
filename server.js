/**
 * server.js - DAA Mother Server (The SQLite Brain)
 * ===============================================
 * Project: DAA Digital Advanced Assistant
 * Version: 1.8 (Persistent SQLite Memory)
 * * Logic:
 * - Stores all conversations in ./memory/daa_memory.db
 * - Injects global history into every AI request (Gemini & Ollama).
 * - Handles base64 vision data from PC-Agent.
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const persona = require('./persona');

const app = express();

// INCREASE LIMITS: Essential for handling high-res base64 images from the agent
app.use(bodyParser.json({ limit: '15mb' }));
app.use(cors());

const PORT = process.env.PORT || 3500;
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
const genAI = new GoogleGenerativeAI(GOOGLE_API_KEY);

// --- SQLITE DATABASE SETUP ---
// We place the database file inside a dedicated 'memory' folder
const MEMORY_DIR = path.join(__dirname, 'memory');
const dbPath = path.join(MEMORY_DIR, 'daa_memory.db');

// Ensure the memory directory exists
if (!fs.existsSync(MEMORY_DIR)) {
    fs.mkdirSync(MEMORY_DIR);
    console.log(">>> Created Memory Directory: ./memory");
}

const db = new sqlite3.Database(dbPath, (err) => {
    if (err) console.error(">>> SQLite Connection Error:", err);
    else console.log(`>>> SQLite Brain Online: ${dbPath}`);
});

// Initialize the table if it doesn't exist. We store role, text content, and base64 images.
db.run(`CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    content TEXT,
    image TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)`);

// --- DATABASE HELPERS ---

/**
 * Loads history from SQLite.
 * If user asks to "summarize" (summera), we fetch more context (150 msgs).
 */
function getGlobalHistoryFromDB(fetchMore = false) {
    const limit = fetchMore ? 150 : 60;
    return new Promise((resolve, reject) => {
        db.all(`SELECT role, content, image FROM (SELECT * FROM history ORDER BY id DESC LIMIT ${limit}) ORDER BY id ASC`, [], (err, rows) => {
            if (err) reject(err);
            else resolve(rows || []);
        });
    });
}

/**
 * Saves a message (User or Assistant) to the SQLite persistent storage.
 */
function saveToDB(role, content, image = null) {
    const stmt = db.prepare("INSERT INTO history (role, content, image) VALUES (?, ?, ?)");
    stmt.run(role, content, image);
    stmt.finalize();
}

console.log("--- DAA MOTHER SERVER STARTING ---");

// --- API ENDPOINTS ---

// Returns the persona settings to the PC-Agent
app.get('/api/persona', (req, res) => {
    console.log(`[SYS] Sending Persona to Agent at ${req.ip}`);
    res.json({ name: persona.ASSISTANT_NAME, instructions: persona.ASSISTANT_PERSONA });
});

// Returns available models (Gemini Cloud + Ollama Local)
app.get('/api/models', async (req, res) => {
    let allModels = [];

    // Cloud Models (Gemini)
    if (GOOGLE_API_KEY) {
        try {
            const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${GOOGLE_API_KEY}`;
            const response = await fetch(url);
            const data = await response.json();
            allModels = allModels.concat(data.models
                .filter(m => m.name.includes('gemini') && m.supportedGenerationMethods.includes('generateContent'))
                .map(m => ({ id: m.name.replace('models/', ''), name: `☁️ ${m.displayName}` })));
        } catch (e) { console.log("[SYS] Gemini Fetch failed or skipped."); }
    }

    // Local Models (Ollama)
    try {
        const response = await fetch('http://127.0.0.1:11434/api/tags');
        if (response.ok) {
            const data = await response.json();
            allModels = allModels.concat(data.models.map(m => ({ id: m.name, name: `🏠 Ollama: ${m.name}` })));
        }
    } catch (e) { console.log("[SYS] Ollama not found locally."); }

    res.json(allModels);
});

// --- MAIN CHAT ROUTE (MEMORY & VISION) ---
app.post('/api/chat', async (req, res) => {
    const { messages, model } = req.body;
    const currentModel = model || "gemini-1.5-flash";
    const lastIncoming = messages[messages.length - 1];
    const userText = (lastIncoming.content || "").toLowerCase();

    try {
        // 1. Determine if we need deep memory (summarization)
        const isSummarize = userText.includes("summera") || userText.includes("sammanfatta") || userText.includes("minns du");

        // 2. Load persistent history from SQLite
        let chatHistory = await getGlobalHistoryFromDB(isSummarize);

        // 3. Save current user message to DB
        saveToDB('user', lastIncoming.content, lastIncoming.image || null);

        console.log(`> Chat Request [${currentModel}]: Memory Loaded (${chatHistory.length} msgs)`);

        // --- HANDLER: OLLAMA (Local) ---
        if (!currentModel.includes('gemini')) {
            const ollamaMessages = chatHistory.map(msg => ({
                role: msg.role,
                content: msg.content,
                ...(msg.image && { images: [msg.image] })
            }));
            // Add current message to the prompt
            ollamaMessages.push({ role: 'user', content: lastIncoming.content, ...(lastIncoming.image && { images: [lastIncoming.image] }) });

            const response = await fetch('http://127.0.0.1:11434/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: currentModel, messages: ollamaMessages, stream: false })
            });
            const data = await response.json();
            const aiText = data.message.content;

            saveToDB('assistant', aiText);
            return res.send(aiText);
        }

        // --- HANDLER: GEMINI (Cloud) ---
        const aiModel = genAI.getGenerativeModel({
            model: currentModel,
            systemInstruction: persona.ASSISTANT_PERSONA
        });

        // Format persistent history for Gemini's startChat
        const geminiHistory = chatHistory.map(msg => ({
            role: msg.role === 'assistant' ? 'model' : 'user',
            parts: [{ text: msg.content || " " }, ...(msg.image ? [{ inlineData: { mimeType: "image/jpeg", data: msg.image } }] : [])]
        }));

        // Current message parts
        const lastParts = [{ text: lastIncoming.content || " " }];
        if (lastIncoming.image) {
            lastParts.push({ inlineData: { mimeType: "image/jpeg", data: lastIncoming.image } });
        }

        const chat = aiModel.startChat({ history: geminiHistory });
        const result = await chat.sendMessageStream(lastParts);

        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        let fullAiResp = "";

        for await (const chunk of result.stream) {
            const chunkText = chunk.text();
            fullAiResp += chunkText;
            res.write(chunkText);
        }

        // 4. Save Nova's response back to persistent memory
        saveToDB('assistant', fullAiResp);
        res.end();

    } catch (error) {
        console.error(">>> Chat Pipeline Error:", error.message);
        res.status(500).send("Nova Error: " + error.message);
    }
});

// --- SERVER BOOT ---
app.listen(PORT, '0.0.0.0', () => {
    console.log(`--- DAA MOTHER ONLINE (SQLite Memory Enabled) ---`);
    console.log(`--- PORT: ${PORT} | MEMORY: ./memory/daa_memory.db ---`);
});