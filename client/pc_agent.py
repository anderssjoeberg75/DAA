"""
pc_agent.py - Local PC Muscle
----------------------------
Run this on your Windows/Mac to allow the server to control your OS.
Install requirements: pip install flask
"""

from flask import Flask, request
import subprocess
import os

app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    action = data.get("action")
    target = data.get("target")

    print(f"Received command: {action} on {target}")

    if action == "open_app":
        try:
            # 'start' is specific to Windows. Use 'open' for Mac.
            subprocess.Popen(f"start {target}", shell=True)
            return {"status": "success", "message": f"Execution started for {target}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return {"status": "ignored", "message": "Unknown action"}

if __name__ == "__main__":
    # Listen on all interfaces on port 5001
    app.run(host="0.0.0.0", port=5001)
