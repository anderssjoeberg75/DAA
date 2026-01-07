"""
tools/google_calendar.py
------------------------
Handles all Google Calendar API interactions and tool definitions.
"""
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to the key file (assumed to be in the parent directory)
SERVICE_ACCOUNT_FILE = 'service-account.json'

def get_calendar_service():
    """Authenticates and returns the Google Calendar service object."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Missing {SERVICE_ACCOUNT_FILE} in root directory.")

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(args):
    """
    Creates an event in the primary Google Calendar.
    Args: summary, startTime, endTime, description (optional)
    """
    try:
        service = get_calendar_service()
        event = {
            'summary': args.get('summary'),
            'description': args.get('description', ''),
            'start': {'dateTime': args.get('startTime'), 'timeZone': 'Europe/Stockholm'},
            'end': {'dateTime': args.get('endTime'), 'timeZone': 'Europe/Stockholm'},
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return {"success": True, "link": created_event.get('htmlLink')}
    except Exception as e:
        print(f"Calendar Error: {e}")
        return {"success": False, "error": str(e)}

# Definition for Gemini's function calling
calendar_tool_definition = {
    "name": "create_calendar_event",
    "description": "Create a new appointment or event in the user's Google Calendar.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "summary": {"type": "STRING", "description": "Title of the event"},
            "startTime": {"type": "STRING", "description": "ISO format timestamp"},
            "endTime": {"type": "STRING", "description": "ISO format timestamp"},
            "description": {"type": "STRING", "description": "Optional notes"}
        },
        "required": ["summary", "startTime", "endTime"]
    }
}