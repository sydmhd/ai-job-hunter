"""
scripts/setup_gmail_oauth.py — One-time Gmail OAuth2 authentication setup.

Run this ONCE on your local machine to generate the token.json file.
Then copy token.json to your server / GitHub secrets.

Usage: python scripts/setup_gmail_oauth.py
"""

import os
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow
from config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_SCOPES


def setup_oauth():
    print("\n" + "=" * 60)
    print("  Gmail OAuth2 Setup")
    print("=" * 60)
    print("""
BEFORE RUNNING THIS SCRIPT:
  1. Go to https://console.cloud.google.com
  2. Create a project (or use existing)
  3. Enable the Gmail API
  4. Go to Credentials → Create OAuth 2.0 Client ID
  5. Application type: Desktop app
  6. Download the JSON file
  7. Save it to: data/gmail_credentials.json
  8. Then run this script
""")

    if not os.path.exists(GMAIL_CREDENTIALS_PATH):
        print(f"❌ Credentials file not found at: {GMAIL_CREDENTIALS_PATH}")
        print("   Please follow the steps above and try again.")
        sys.exit(1)

    print(f"✅ Found credentials at: {GMAIL_CREDENTIALS_PATH}")
    print("\n🌐 Opening browser for Google OAuth consent...\n")

    flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)

    with open(GMAIL_TOKEN_PATH, "w") as token:
        token.write(creds.to_json())

    print(f"\n✅ Token saved to: {GMAIL_TOKEN_PATH}")
    print("\n📋 NEXT STEPS:")
    print("   • The token auto-refreshes — you won't need to re-auth")
    print(f"   • For GitHub Actions: add contents of {GMAIL_TOKEN_PATH}")
    print("     as a secret named GMAIL_TOKEN_JSON\n")


if __name__ == "__main__":
    setup_oauth()
