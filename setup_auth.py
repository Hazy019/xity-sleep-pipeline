"""
Modern Stoic Pipeline — Google OAuth2 Token Generator v4

Purpose:
    Run this ONCE before the pipeline to authenticate with Google.
    Consolidates Drive, YouTube, and Analytics into a single refreshable token.
"""

import sys
from pathlib import Path

# Add src to path so we can import auth
sys.path.append(str(Path(__file__).parent))
from src.auth import get_google_credentials

def main():
    print("\n" + "="*60)
    print("  Modern Stoic Pipeline — Google OAuth2 Token Generator v4")
    print("="*60)
    print("\nThis will set up a master token for:")
    print("  - Google Drive (Upload/Download)")
    print("  - YouTube Data API (Video Uploads)")
    print("  - YouTube Analytics (Reporting)")
    print("\nUse --manual if you are setting this up for a remote client.")
    print("="*60 + "\n")

    try:
        is_manual = "--manual" in sys.argv
        get_google_credentials(manual=is_manual)
        
        print("\n" + "="*60)
        print("  ✅ All services authorized and saved to config/master_token.json")
        print("  The pipeline is ready for autonomous operation.")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled.")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")

if __name__ == "__main__":
    main()