"""
tools/gcal_core.py - Google Calendar Module for DAA
===================================================
Project: DAA Digital Advanced Assistant
Description: Fetches upcoming events from Google Calendar via Service Account.
Author: Malte (DAA) / User
"""

import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION ---
# We navigate up from 'tools' to root, then into 'config'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_PATH = os.path.join(BASE_DIR, "config", "google_calendar_key.json")

# Read-only scope is sufficient for checking schedule
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_calendar_events(max_results=5):
    """
    Connects to Google Calendar API and retrieves the next upcoming events.
    Returns a formatted string suitable for TTS (Text-to-Speech).
    """
    print(f"[GCAL] Attempting to read calendar with key: {KEY_PATH}")

    # 1. Validation: Check if key exists
    if not os.path.exists(KEY_PATH):
        return "Error: Missing 'google_calendar_key.json' in the config folder."

    try:
        # 2. Authentication
        creds = service_account.Credentials.from_service_account_file(
            KEY_PATH, scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)

        # 3. Time Setup: Get current time in UTC ISO format
        now = datetime.datetime.utcnow().isoformat() + 'Z'

        # 4. Fetch Events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return "I couldn't find any upcoming events in your calendar."

        # 5. Format Output for Speech
        output_text = "Here is your upcoming schedule: "
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))

            # Simple formatting: Remove seconds and timezone info for cleaner speech
            # Input: "2026-01-11T14:00:00+01:00" -> Output: "2026-01-11 14:00"
            clean_time = start.replace('T', ' ').split('+')[0][:16]

            summary = event.get('summary', 'No Title')
            output_text += f"At {clean_time}: {summary}. "

        return output_text

    except Exception as e:
        print(f"[GCAL ERROR] {e}")
        return f"An error occurred while reading the calendar: {str(e)}"