"""
Run this script ONCE locally to generate gmail_token.json.
The browser will open for Google login.
After login, gmail_token.json is saved and used by the backend.

Usage:
    python generate_gmail_token.py
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "gmail_credentials.json")
TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "gmail_token.json")


def main():
    creds = None

    # check if token already exists
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # if no valid credentials, login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("No valid token found. Starting login flow...")
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"Error: {CREDENTIALS_PATH} not found. Please provide the credentials JSON file.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            print("Login successful.")

        # save the token for next time
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"Token saved to: {TOKEN_PATH}")
    else:
        print("Token is already valid. No action needed.")


if __name__ == "__main__":
    main()
