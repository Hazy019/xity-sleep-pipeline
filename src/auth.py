import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# Path to the OAuth 2.0 Client ID json file from Google Cloud Console
CREDENTIALS_FILE = Path("config/credentials.json")

# Path to the cached token file that stores the user's access and refresh tokens
# We use a single master_token.json as requested for both YouTube and Sheets
TOKEN_FILE = Path("config/master_token.json")

# Combined scopes for YouTube, Google Sheets, Google Drive, and YouTube Analytics
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def get_google_credentials(manual=False):
    """
    Handles the OAuth2 authentication flow for Google APIs.
    
    Args:
        manual (bool): If True, generates an auth URL and waits for user input 
                      instead of opening a local browser. useful for remote clients.
    
    Returns:
        google.oauth2.credentials.Credentials: Valid Google API credentials.
    """
    creds = None
    
    # 1. Attempt to load existing credentials from the token file
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            print(f"[auth] Error loading existing token: {e}")
    
    # 2. If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[auth] Refreshing expired credentials...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[auth] Refresh failed: {e}. Re-authenticating...")
                creds = None
        
        if not creds or not creds.valid:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Credentials file missing at {CREDENTIALS_FILE}. "
                    "Please download your 'OAuth 2.0 Client ID' JSON from Google Cloud Console."
                )
                
            print("[auth] Starting authentication flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), 
                SCOPES,
                redirect_uri='http://localhost:8080'
            )
            
            if manual:
                # Manual flow: Generate URL and wait for response
                auth_url, _ = flow.authorization_url(
                    access_type='offline',
                    prompt='consent',
                    include_granted_scopes='true'
                )
                print("\n" + "="*60)
                print("GOOGLE AUTHORIZATION LINK")
                print("="*60)
                print(f"\n{auth_url}\n")
                print("="*60)
                print("1. Send the link above to the client.")
                print("2. After they 'Allow', they will be redirected to a broken page.")
                print("3. Ask them to copy the FULL URL from their browser address bar.")
                print("4. Paste that URL here.")
                print("="*60 + "\n")
                
                response_url = input("Paste the redirected URL here: ").strip()
                flow.fetch_token(authorization_response=response_url)
                creds = flow.credentials
            else:
                print("IMPORTANT: When the browser opens, select the Brand Account (Modern Stoic).")
                # Using select_account consent and access_type='offline' ensures we get a refresh token
                creds = flow.run_local_server(
                    port=8080, 
                    prompt='select_account consent',
                    access_type='offline'
                )
            
        # 3. Save the credentials for the next run
        print(f"[auth] Saving credentials to {TOKEN_FILE}")
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
        
        # 4. Verify which YouTube channel was authorized
        _verify_channel(creds)

    return creds

def _verify_channel(creds):
    """Prints the authorized channel name for verification."""
    try:
        from googleapiclient.discovery import build as _build
        yt = _build("youtube", "v3", credentials=creds, cache_discovery=False)
        ch = yt.channels().list(part="snippet", mine=True).execute()
        items = ch.get("items", [])
        if items:
            ch_name = items[0]["snippet"]["title"]
            ch_id   = items[0]["id"]
            print(f"\n✓ Authenticated channel: '{ch_name}' (ID: {ch_id})")
        else:
            print("[auth] WARNING: Could not detect channel. Please verify manually.")
    except Exception as e:
        print(f"[auth] Channel check skipped: {e}")

if __name__ == "__main__":
    import sys
    # Test authentication
    try:
        is_manual = "--manual" in sys.argv
        c = get_google_credentials(manual=is_manual)
        print("✓ Authentication successful.")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
