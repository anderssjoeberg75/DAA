"""
pc_agent.py - The Muscle
------------------------
Runs on the local Windows PC.
Executes commands received from the central DAA server.
"""
import os
import subprocess
import platform
from flask import Flask, request, jsonify

app = Flask(__name__)

# Security: Only allow commands from the specific server IP to prevent unauthorized access
# Update this with your Ubuntu Server's IP address (e.g., '192.168.1.50')
ALLOWED_SERVER_IP = "192.168.1.XX"

def open_application(app_name):
    """
    Attempts to open an application on Windows.
    """
    system = platform.system()

    if system == "Windows":
        try:
            # Common paths can be added here, or rely on system PATH / Start Menu indexing
            # 'start' command in Windows cmd can often launch apps by name
            subprocess.Popen(f'start {app_name}', shell=True)
            return True, f"Command sent to open {app_name}"
        except Exception as e:
            return False, str(e)

    elif system == "Darwin": # macOS
        try:
            subprocess.Popen(["open", "-a", app_name])
            return True, f"Opening {app_name} on macOS"
        except Exception as e:
            return False, str(e)

    return False, "Unsupported Operating System"

@app.route('/execute', methods=['POST'])
def execute_command():
    """
    Endpoint to receive commands from the central brain.
    Expected JSON: {"action": "open_app", "target": "spotify"}
    """
    # Optional: IP Check
    # if request.remote_addr != ALLOWED_SERVER_IP:
    #     return jsonify({"status": "error", "message": "Unauthorized IP"}), 403

    data = request.json
    action = data.get('action')
    target = data.get('target')

    print(f"📥 Received command: {action} -> {target}")

    if action == "open_app":
        success, message = open_application(target)
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "error", "message": message})

    return jsonify({"status": "error", "message": "Unknown action"}), 400

if __name__ == '__main__':
    print("🚀 DAA PC Agent running on port 5001...")
    # host='0.0.0.0' allows connections from external IPs (like your Ubuntu server)
    app.run(host='0.0.0.0', port=5001)