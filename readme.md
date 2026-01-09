# 🌌 DAA - Digital Advanced Assistant

DAA is a modular AI assistant architecture designed to bridge the gap between cloud-based AI and local system control. The **"Brain"** (FastAPI) runs on a central Ubuntu server, while the **"Muscle"** (Python Agent) runs on your local PC to execute system commands.

---

## 🛠 1. System Architecture

* **Central Server (Ubuntu):** Orchestrates AI logic (Gemini/Ollama), manages Google Calendar via Service Account, and delegates tasks.
* **Local Agent (PC):** A lightweight Flask service on Windows/Mac that executes OS commands like opening applications.
* **Web UI:** A responsive, Markdown-enabled frontend served by the Ubuntu server on port `3000`.

---

## 📋 2. Prerequisites

### 🌐 Network Setup
* The **Ubuntu Server** must be able to reach the **Local PC's IP** on port `5001`.
* The **PC Firewall** must allow inbound traffic on port `5001` from the server's local IP.

### 📅 Google Calendar Setup
* Requires a Google Cloud Project with the **Calendar API** enabled.
* A **Service Account** JSON key named `service-account.json` must be placed in the server root.
* **Permissions:** The Service Account email must be added to your Google Calendar sharing settings. (See [Tools](#tools-google-calendar-setup) section).

---

## 🚀 3. Server Installation (Ubuntu)

### Step 3.1: Prepare the Environment
```bash
sudo mkdir -p /opt/daa
cd /opt/daa/
python3 -m venv venv
source venv/bin/activate
```

### Step 3.2: Install Dependencies
```bash
pip install fastapi uvicorn requests google-api-python-client google-auth
```

### Step 3.3: Configure the Brain
* Update `PC_CLIENT_IP` in `main.py` with your local PC's static IP address.
* Ensure `persona.js` and `service-account.json` are placed in the root directory.
* If using Gemini, ensure your `GEMINI_API_KEY` is ready for the service configuration in the next step.

---

## ⚙️ 4. Deployment (Systemd Service)

To keep the assistant running 24/7 as a background process named `assistant`.

### Step 4.1: Create the Service File
```bash
sudo nano /etc/systemd/system/assistant.service
```
### Step 4.2: Configuration
Paste the following into the file (make sure to update the path and your API key):

```ini
[Unit]
Description=Digital Advanced Assistant Service (DAA)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/daa
Environment="GEMINI_API_KEY=your_actual_key_here"
# Using the python interpreter inside the virtual environment
ExecStart=/opt/daa/venv/bin/python3 main.py
Restart=always
RestartSec=5
User=Root
Group=Root

[Install]
WantedBy=multi-user.target
```
### Step 4.3: Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable assistant
sudo systemctl start assistant
```
### Step 4.4: Monitoring
* **Status check:** `sudo systemctl status assistant`
* **Real-time logs:** `journalctl -u assistant -f`

---

## 💻 5. Local PC Agent Installation (Windows/Mac)
## Installation of Python 3 on Windows 11

To contribute to or run the **DAA Digital Advanced Assistant**, you need Python 3 installed on your system. Follow these steps for a correct setup:

### 1. Download the Installer
* Visit the official Python website: [python.org/downloads](https://www.python.org/downloads/windows/).
* Download the latest stable release (e.g., Python 3.12 or 3.13).

### 2. Run the Setup
* Launch the `.exe` installer.
* **IMPORTANT**: Check the box that says **"Add Python.exe to PATH"** at the bottom of the window. This ensures you can run Python from any terminal.
* Click **Install Now**.

### 3. Finalize Installation
* At the end of the installation, if prompted with **"Disable path length limit"**, click it. This prevents issues with long file paths in Windows.

### 4. Verify the Installation
Open your terminal (PowerShell or CMD) and run the following commands to ensure everything is set up correctly:

```bash
# Check Python version
python --version

# Check Pip (Python Package Manager) version
pip --version
```
### Install client 

1. **Navigate** to the client directory on your local PC where `pc_agent.py` is located.
2. **Install Flask:**
   ```bash
   pip install flask
   ```
3. **Run the Agent:**
   ```
    python pc_agent.py
   ```
   Note: Ensure your PC firewall allows inbound traffic on port 5001 from the Ubuntu Server's IP address.

## 📂 6. Project File Map

```text
daa/
├── main.py                # Server Entry Point (FastAPI)
├── persona.js             # Persona Configuration
├── service-account.json   # Google API Key
├── venv/                  # Python Virtual Environment
├── tools/
│   └── google_calendar.py # Calendar Tool Module
├── public/
    └── index.html         # Web Interface
    └── client/
        └── pc_agent.py        # Local PC Command Executor (The Muscle)
