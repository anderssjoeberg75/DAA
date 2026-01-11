"""
pc_agent.py - DAA Digital Advanced Assistant
============================================
Project: DAA (Digital Advanced Assistant)
Version: 1.6 (Server-Memory Optimized)

Key Features:
- SERVER-SIDE MEMORY: Optimized to let 'server.js' handle all SQLite history.
- UNIFIED SETTINGS: All keys and configs are in 'settings.json'.
- SWAPPED CAMERAS: Camera 1 (Main) and Camera 0 (PiP).
- DETAILED ANNOTATIONS: English documentation for every logic block.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

# --- PRE-INIT: DPI & ENVIRONMENT ---
# Prevents Windows Scaling issues and access denied errors during startup.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# --- HELPER FUNCTIONS ---
def get_time():
    """Returns a formatted timestamp string for system logs."""
    return datetime.now().strftime("[%H:%M:%S]")

# --- CONFIGURATION MANAGER ---
# We use settings.json to store everything from API keys to hardware IDs.
SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "server_url": "http://192.168.107.15:3500",
    "elevenlabs_api_key": "YOUR_KEY_HERE",
    "elevenlabs_voice_id": "YOUR_VOICE_ID_HERE",
    "elevenlabs_model_id": "eleven_turbo_v2_5",
    "camera": {
        "main_index": 0,
        "pip_index": 1,
        "brightness": 30,
        "sensitivity": 5000,
        "cooldown": 2.5
    },
    "turbo": {
        "img_size": 350,
        "quality": 35
    }
}

def load_settings():
    """Loads configuration from JSON or creates a default one if missing."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, SETTINGS_FILE)
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
    with open(file_path, "r") as f:
        return json.load(f)

# Global Configuration Object
CONFIG = load_settings()

# --- LIBRARIES ---
import requests
import asyncio
import threading
import queue
import base64
import websockets
import pyaudio
import pyautogui
import math
import io
import cv2
import markdown
import webbrowser
import subprocess
import speech_recognition as sr
from PIL import Image

# PySide6 handles the Cyberpunk-styled Graphical User Interface
from PySide6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QLabel,
                               QVBoxLayout, QWidget, QLineEdit, QHBoxLayout,
                               QPushButton, QFrame, QComboBox, QCheckBox)
from PySide6.QtCore import QTimer, Qt, Signal, Slot, QThread, QObject
from PySide6.QtGui import QColor, QPainter, QBrush, QVector3D, QMatrix4x4, QTextCursor, QPixmap, QImage

# Mapping CONFIG into local variables for easier access
SERVER_URL = CONFIG["server_url"]
ELEVENLABS_API_KEY = CONFIG["elevenlabs_api_key"]
VOICE_ID = CONFIG["elevenlabs_voice_id"]
MODEL_ID = CONFIG["elevenlabs_model_id"]

MAIN_CAM_INDEX = CONFIG["camera"]["main_index"]
PIP_CAM_INDEX = CONFIG["camera"]["pip_index"]
BRIGHTNESS = CONFIG["camera"]["brightness"]
MOTION_SENSITIVITY = CONFIG["camera"]["sensitivity"]
MOTION_COOLDOWN = CONFIG["camera"]["cooldown"]
IMG_SIZE = CONFIG["turbo"]["img_size"]
IMG_QUALITY = CONFIG["turbo"]["quality"]

# ==========================================
# --- SYSTEM ACTION HANDLERS ---
# ==========================================

def handle_browser(url):
    """Opens a URL or Spotify URI in the default web browser."""
    webbrowser.open(url.strip())

def handle_cmd(command):
    """Executes a local shell command."""
    subprocess.Popen(command, shell=True)

def handle_key(key_command):
    """Triggers global media keys on the Windows OS level."""
    k = key_command.strip().lower()
    if k == "play" or k == "pause": pyautogui.press("playpause")
    elif k == "next": pyautogui.press("nexttrack")
    elif k == "prev":
        pyautogui.press("prevtrack")
        pyautogui.press("prevtrack")
    elif k == "volup": pyautogui.press("volumeup")
    elif k == "voldown": pyautogui.press("volumedown")

# ==========================================
# --- WORKER THREADS (LOGIC) ---
# ==========================================

class LogSignal(QObject):
    """Thread-safe signal for passing text logs to the GUI."""
    log = Signal(str)

class WebcamWorker(QThread):
    """
    Captures dual-camera feed and processes motion detection.
    Optimized: Cam 1 is the main high-res view, Cam 0 is the small PiP.
    """
    image_update = Signal(QImage); status_log = Signal(str); motion_detected = Signal()

    def __init__(self):
        super().__init__(); self.running = False; self.cf = None; self.prev = None; self.skip = 0

    def run(self):
        self.running = True
        self.status_log.emit(f"{get_time()} [CAM] Initializing Dual Feed...")

        # Opening both cameras with DirectShow for maximum Windows compatibility
        cap_a = cv2.VideoCapture(MAIN_CAM_INDEX, cv2.CAP_DSHOW) # Index 0
        cap_b = cv2.VideoCapture(PIP_CAM_INDEX, cv2.CAP_DSHOW)  # Index 1

        while self.running:
            # Capture logic: Main view (cap_b) and Overlay view (cap_a)
            ret_main, frame_main = cap_b.read()
            ret_pip, frame_pip = cap_a.read()

            # Fail-safe: If Camera 1 fails, use Camera 0 as the primary view
            if not ret_main:
                if ret_pip:
                    frame_main = frame_pip
                    ret_main = True
                    frame_pip = None
                else:
                    QThread.msleep(100); continue

            # --- MOTION DETECTION (Using main view) ---
            if self.skip == 0 and frame_main is not None:
                gray = cv2.cvtColor(frame_main, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)
                if self.prev is not None:
                    diff = cv2.absdiff(self.prev, gray)
                    thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
                    if cv2.countNonZero(thresh) > MOTION_SENSITIVITY: self.motion_detected.emit()
                self.prev = gray
            self.skip = (self.skip + 1) % 5

            # --- PICTURE-IN-PICTURE (PIP) ---
            if frame_main is not None and frame_pip is not None:
                h, w, _ = frame_main.shape; sc = 0.3
                nw = int(w*sc); nh = int(frame_pip.shape[0]*(nw/frame_pip.shape[1])); sm = cv2.resize(frame_pip, (nw, nh))
                frame_main[h-nh-20:h-20, w-nw-20:w-20] = sm
                cv2.rectangle(frame_main, (w-nw-20, h-nh-20), (w-20, h-20), (255, 255, 255), 2)

            if BRIGHTNESS > 0 and frame_main is not None:
                frame_main = cv2.convertScaleAbs(frame_main, alpha=1, beta=BRIGHTNESS)

            self.cf = frame_main
            if frame_main is not None:
                rgb = cv2.cvtColor(frame_main, cv2.COLOR_BGR2RGB); h, w, ch = rgb.shape
                qt_img = QImage(rgb.data, w, h, ch*w, QImage.Format_RGB888).scaled(260, 200, Qt.KeepAspectRatio)
                self.image_update.emit(qt_img)

            QThread.msleep(30)

        cap_a.release()
        cap_b.release()

    def stop(self): self.running = False; self.wait()
    def get_snapshot(self):
        """Prepares a Turbo JPEG (downscaled) for AI vision analysis."""
        if self.cf is None: return None, 0
        img = Image.fromarray(cv2.cvtColor(self.cf, cv2.COLOR_BGR2RGB)); img.thumbnail((IMG_SIZE, IMG_SIZE))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=IMG_QUALITY)
        return base64.b64encode(buf.getvalue()).decode('utf-8'), len(buf.getvalue())

class AudioRecorder(QThread):
    """Records audio from mic and performs Speech-to-Text via Google."""
    finished = Signal(str); started = Signal(); stopped = Signal()
    def __init__(self, log): super().__init__(); self.l = log; self.r = sr.Recognizer()
    def run(self):
        self.started.emit(); self.l.log.emit("[MIC] Listening...")
        try:
            with sr.Microphone() as s:
                self.r.adjust_for_ambient_noise(s, 0.5)
                audio_data = self.r.listen(s, timeout=5, phrase_time_limit=10)
            self.stopped.emit(); self.l.log.emit("[MIC] Processing...")
            text = self.r.recognize_google(audio_data, language="sv-SE")
            self.finished.emit(text)
        except Exception as e: self.stopped.emit(); self.l.log.emit(f"[MIC ERR] {e}")

class TTSWorker(QThread):
    """Streams text to ElevenLabs and plays back high-fidelity voice."""
    speaking = Signal(bool)
    def __init__(self, log): super().__init__(); self.q = queue.Queue(); self.running = True; self.mute = True; self.l = log
    def add(self, t):
        if not self.mute and t.strip(): self.q.put(t.strip())
    async def loop(self):
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}&output_format=pcm_24000"
        while self.running:
            if self.q.empty() or self.mute: await asyncio.sleep(0.1); continue
            txt = self.q.get(); self.speaking.emit(True)
            try:
                async with websockets.connect(uri) as ws:
                    await ws.send(json.dumps({"text":" ","xi_api_key":ELEVENLABS_API_KEY})); await ws.send(json.dumps({"text":txt})); await ws.send(json.dumps({"text":""}))
                    while True:
                        m = await ws.recv(); d = json.loads(m)
                        if d.get("audio"): pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1, rate=24000, output=True).write(base64.b64decode(d["audio"]))
                        if d.get("isFinal"): break
            except Exception as e: self.l.log.emit(f"[TTS ERR] {e}")
            self.speaking.emit(False); self.q.task_done()
    def run(self): asyncio.new_event_loop().run_until_complete(self.loop())

class AgentWorker(QObject):
    """
    Client Interface for the Mother Server.
    MEMORY: We no longer store local history here. We let the Server's SQLite DB handle it.
    """
    received = Signal(str); signal = Signal(str, str, str); lost = Signal()
    def __init__(self, tts, log): super().__init__(); self.tts = tts; self.l = log; self.prompt = None; self.signal.connect(self.process)
    def process(self, text, mid, img):
        is_auto = (text == "[AUTO_CHECK]")
        if not is_auto: self.l.log.emit(f"[NET] Sending to Brain...")

        # We only send the CURRENT message. The Server will inject the context from daa_memory.db
        payload = {"role": "user", "content": text}
        if img: payload["image"] = img
        msgs = [payload]

        resp = ""; buf = ""
        try:
            with requests.post(f"{SERVER_URL}/api/chat", json={"model":mid, "messages":msgs}, stream=True, timeout=60) as r:
                r.raise_for_status()
                for chunk in r.iter_content(None):
                    if chunk:
                        t = chunk.decode("utf-8"); resp += t; buf += t
                        # Parse [DO:...] commands in real-time
                        if "[DO:" in buf and "]" in buf:
                            s = buf.find("[DO:"); e = buf.find("]", s); tag = buf[s:e+1]; content = tag[4:-1]
                            if "|" in content:
                                atype, adata = content.split("|", 1)
                                try:
                                    if atype.strip()=="BROWSER": handle_browser(adata)
                                    elif atype.strip()=="CMD": handle_cmd(adata)
                                    elif atype.strip()=="KEY": handle_key(adata)
                                    elif atype.strip()=="WAIT": time.sleep(float(adata))
                                except: pass
                            buf = buf.replace(tag, ""); resp = resp.replace(tag, ""); t = ""
                        self.received.emit(resp)
                        if not is_auto and any(x in buf for x in ".?!") and "[DO:" not in buf:
                            self.tts.add(buf.replace("*","").replace("#","")); buf = ""
        except Exception as e: self.l.log.emit(f"[NET ERR] {e}"); self.lost.emit()

# ==========================================
# --- UI AND MAIN WINDOW ---
# ==========================================

class AIAnimationWidget(QWidget):
    """Rotating 3D Orb visualizer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle_y = 0; self.angle_x = 0; self.pulse_angle = 0
        self.is_speaking = False; self.is_listening = False
        self.points = self.create_points()
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_orb); self.timer.start(30)
    def set_speaking(self, s): self.is_speaking = s; self.update()
    def set_listening(self, l): self.is_listening = l; self.update()
    def create_points(self, r=85, n=20):
        p = []
        for i in range(n + 1):
            lat = math.pi * (-0.5 + i / n); y = r * math.sin(lat); xy_r = r * math.cos(lat)
            for j in range(30):
                lon = 2 * math.pi * (j / 30); p.append(QVector3D(xy_r * math.cos(lon), y, xy_r * math.sin(lon)))
        return p
    def update_orb(self):
        self.angle_y += 0.8; self.angle_x += 0.2
        if self.is_speaking or self.is_listening: self.pulse_angle += 0.2
        self.update()
    def paintEvent(self, e):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing); painter.translate(self.width()/2, self.height()/2)
        pulse = 1.0 + ((1 + math.sin(self.pulse_angle)) * 0.05) if (self.is_speaking or self.is_listening) else 1.0
        rot = QMatrix4x4(); rot.rotate(self.angle_y, 0, 1, 0); rot.rotate(self.angle_x, 1, 0, 0)
        proj = sorted([((rp.x()*z)*pulse, (rp.y()*z)*pulse, 2+((rp.z()+60)/100)*3, int(50+205*((rp.z()+60)/100))) for pt in self.points for rp in [rot.map(pt)] for z in [300/(300+rp.z())]], key=lambda x:x[2])
        for x,y,s,a in proj:
            c = QColor(255, 100, 100, a) if self.is_speaking else (QColor(100, 255, 100, a) if self.is_listening else QColor(0, 255, 255, a))
            painter.setBrush(QBrush(c)); painter.setPen(Qt.NoPen); painter.drawEllipse(int(x), int(y), int(s), int(s))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("DAA Digital Advanced Assistant"); self.resize(1280, 750)
        self.setStyleSheet("""QMainWindow { background-color: #050510; } QWidget { color: #c9d1d9; font-family: 'Segoe UI', sans-serif; font-size: 14px; } QTextEdit { background-color: #0a0a1a; border: 1px solid #1f293a; border-radius: 5px; color: #e0e6ed; padding: 10px; } QLineEdit { background-color: #0d1117; border: 1px solid #30363d; padding: 10px; color: #00ffcc; font-weight: bold; } QPushButton { background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 8px; color: #58a6ff; font-weight: bold; } QComboBox { background-color: #0d1117; border: 1px solid #30363d; padding: 5px; color: #00ffcc; } QFrame#Panel { background-color: #0b0e14; border: 1px solid #30363d; border-radius: 8px; } QLabel#Title { color: #58a6ff; font-weight: bold; font-size: 14px; border-bottom: 1px solid #30363d; padding-bottom: 5px; margin-bottom: 10px; }""")

        self.last_auto = datetime.min; self.logger = LogSignal(); self.logger.log.connect(self.add_log)
        self.tts = TTSWorker(self.logger); self.tts.start()
        self.worker = AgentWorker(self.tts, self.logger); self.thread = QThread(); self.worker.moveToThread(self.thread); self.thread.start()

        self.web = WebcamWorker()
        self.web.image_update.connect(self.update_cam); self.web.status_log.connect(self.add_log); self.web.motion_detected.connect(self.on_motion)

        # --- UI LAYOUT ---
        central = QWidget(); self.setCentralWidget(central); layout = QHBoxLayout(central)
        L = QFrame(); L.setObjectName("Panel"); L.setFixedWidth(300); l_lyt = QVBoxLayout(L); lbl_l = QLabel("SYSTEM ACTIVITY"); lbl_l.setObjectName("Title"); l_lyt.addWidget(lbl_l); self.log_v = QTextEdit(); self.log_v.setReadOnly(True); l_lyt.addWidget(self.log_v); layout.addWidget(L)
        C = QVBoxLayout(); self.orb = AIAnimationWidget(); self.orb.setFixedSize(250, 250); C.addWidget(self.orb, 0, Qt.AlignCenter); self.chat_v = QTextEdit(); self.chat_v.setReadOnly(True); C.addWidget(self.chat_v); ib = QHBoxLayout(); btn_mic = QPushButton("🎙️"); btn_mic.clicked.connect(self.start_mic); self.inp = QLineEdit(); self.inp.returnPressed.connect(self.send); btn_s = QPushButton("SEND"); btn_s.clicked.connect(self.send); ib.addWidget(btn_mic); ib.addWidget(self.inp); ib.addWidget(btn_s); C.addLayout(ib); layout.addLayout(C)
        R = QFrame(); R.setObjectName("Panel"); R.setFixedWidth(320); r_lyt = QVBoxLayout(R); lbl_r = QLabel("VISION FEED"); lbl_r.setObjectName("Title"); r_lyt.addWidget(lbl_r); self.v_lbl = QLabel("OFF"); self.v_lbl.setAlignment(Qt.AlignCenter); self.v_lbl.setStyleSheet("background:#000; min-height:250px;"); r_lyt.addWidget(self.v_lbl);
        r_lyt.addWidget(QLabel("Image Source:")); self.src = QComboBox(); self.src.addItems(["Screen","Webcam"]); self.src.setCurrentIndex(1); self.src.currentIndexChanged.connect(self.toggle_src); r_lyt.addWidget(self.src);
        self.chk_a = QCheckBox("⚡ AUTO MOTION"); r_lyt.addWidget(self.chk_a);
        self.chk_v = QCheckBox("👁️ SEND IMAGE"); r_lyt.addWidget(self.chk_v);
        self.m_cmb = QComboBox(); r_lyt.addWidget(QLabel("Model:")); r_lyt.addWidget(self.m_cmb); r_lyt.addStretch();
        self.btn_mut = QPushButton("🔇 UNMUTE"); self.btn_mut.clicked.connect(self.toggle_mute); r_lyt.addWidget(self.btn_mut); layout.addWidget(R)

        self.worker.received.connect(self.update_ui); self.worker.lost.connect(self.reconnect_loop); self.tts.speaking.connect(self.orb.set_speaking)
        self.rec = AudioRecorder(self.logger); self.rec.finished.connect(self.on_voice); self.rec.started.connect(lambda: self.orb.set_listening(True)); self.rec.stopped.connect(lambda: self.orb.set_listening(False))

        self.web.start()
        self.timer = QTimer(); self.timer.timeout.connect(self.connect); QTimer.singleShot(1000, self.connect)

    def add_log(self, t): self.log_v.append(t)
    def start_mic(self): self.rec.start()
    def on_voice(self, t): self.inp.setText(t); self.send()
    def toggle_src(self): (self.web.start() if self.src.currentIndex()==1 else self.web.stop())
    def toggle_mute(self): self.tts.mute = not self.tts.mute; self.btn_mut.setText("🔇 UNMUTE" if self.tts.mute else "🔊 MUTE")
    def update_cam(self, i): self.v_lbl.setPixmap(QPixmap.fromImage(i))
    def on_motion(self):
        if self.chk_a.isChecked() and (datetime.now()-self.last_auto).total_seconds() > MOTION_COOLDOWN:
            self.last_auto = datetime.now(); self.add_log("[AUTO] Motion detected!"); img, _ = self.web.get_snapshot(); self.worker.signal.emit("[AUTO_CHECK]", self.m_cmb.currentData(), img)
    def reconnect_loop(self): (self.timer.start(5000) if not self.timer.isActive() else None)
    def connect(self):
        try:
            d = requests.get(f"{SERVER_URL}/api/persona", timeout=2).json(); self.worker.prompt = {"role":"system","content":d.get('instructions','')}
            self.m_cmb.clear()
            for m in requests.get(f"{SERVER_URL}/api/models", timeout=2).json(): self.m_cmb.addItem(m['name'], m['id'])
            self.add_log("[SYS] Connected."); self.timer.stop()
        except: self.add_log(f"[SYS] Searching for brain..."); self.reconnect_loop()
    def send(self):
        t = self.inp.text(); self.inp.clear(); self.chat_v.clear()
        img = None;
        if self.src.currentIndex()==1: img, _ = self.web.get_snapshot()
        self.worker.signal.emit(t, self.m_cmb.currentData(), img)
    def update_ui(self, t): h = markdown.markdown(t.split("[[")[0], extensions=['fenced_code']); self.chat_v.setHtml(f"<style>pre{{background:#222;padding:5px;}}</style>{h}"); self.chat_v.moveCursor(QTextCursor.End)

if __name__ == "__main__":
    app = QApplication(sys.argv); win = MainWindow(); win.show(); sys.exit(app.exec())