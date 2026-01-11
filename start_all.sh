#!/bin/bash
cd /opt/daa

# Exportera API-nyckeln
export GOOGLE_API_KEY="AIzaSyAG_uPMTAD_rcD0XCLG5b2nDNWHJo6mu8Y"

echo "--- RENSAR PORTAR (3000 & 3500) ---"
sudo fuser -k 3000/tcp > /dev/null 2>&1
sudo fuser -k 3500/tcp > /dev/null 2>&1
sleep 1

echo "--- STARTAR DAA SYSTEM ---"

# 1. Starta Mother (Node) på port 3500
# Vi sätter PORT=3500 här för att vara extra säkra
PORT=3500 node server.js 2>&1 | tee /opt/daa/mother.log &

sleep 2

# 2. Starta Agent (Python) på port 3000
# (Eftersom du ändrat i main.py till 3000 kör vi den nu)
/opt/daa/venv/bin/python3 main.py 2>&1 | tee /opt/daa/agent.log
