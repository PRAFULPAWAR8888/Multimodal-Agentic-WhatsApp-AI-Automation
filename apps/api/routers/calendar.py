"""
Calendar API Router.

Handles OAuth flow for Google Calendar integration.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import os
import json
from google_auth_oauthlib.flow import Flow

from whatsapp_agent.config.settings import get_settings

router = APIRouter(prefix="/calendar", tags=["Calendar"])
settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_FILE = "google_calendar_token.json"


auth_state = {}

def get_google_client_config():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google Client ID and Secret not configured")

    return {
        "web": {
            "client_id": settings.google_client_id,
            "project_id": "whatsapp-ai-platform",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_redirect_uri]
        }
    }


@router.get("/google/login")
async def google_calendar_login(request: Request):
    """Initiates the Google Calendar OAuth2 flow."""
    client_config = get_google_client_config()
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri
    )
    
    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
    
    # Store PKCE code_verifier temporarily
    if hasattr(flow, 'code_verifier'):
        auth_state[state] = flow.code_verifier
        
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_calendar_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handles the OAuth2 callback from Google."""
    if error:
        return {"error": f"Authorization failed: {error}"}
    if not code:
        return {"error": "No authorization code provided"}

    # Allow HTTP localhost for development
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    client_config = get_google_client_config()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri
    )

    # Restore PKCE code_verifier
    if state and state in auth_state:
        flow.code_verifier = auth_state.pop(state)

    try:
        # Fetch token using the authorization code
        flow.fetch_token(code=code)
    except Exception as e:
        return {"error": f"Failed to fetch token: {str(e)}"}
        
    credentials = flow.credentials

    # Save credentials to local file
    creds_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    
    with open(TOKEN_FILE, "w") as token_file:
        json.dump(creds_data, token_file)

    return {"message": "Google Calendar authentication successful! You can close this tab and return to the platform."}
