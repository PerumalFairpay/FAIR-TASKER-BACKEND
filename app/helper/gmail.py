from __future__ import annotations

import base64
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailHelper:
    def __init__(
        self,
        credentials_path: str = "gmail_credentials.json",
        token_path: str = "gmail_token.json",
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_credentials(self) -> Credentials:
        creds = None

        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(self.token_path, "w") as f:
                    f.write(creds.to_json())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
                with open(self.token_path, "w") as f:
                    f.write(creds.to_json())

        return creds

    def _service_client(self):
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def _build_message(
        self,
        to: str,
        subject: str,
        body_html: str,
        sender: str = None,
        reply_to_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        """Build a raw MIME message ready to send via the Gmail API."""
        if sender is None:
            sender = "FairPAY Tech Works <fairpayhrm@gmail.com>"

        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["From"] = sender
        msg["Subject"] = subject

        if reply_to_message_id:
            msg["In-Reply-To"] = reply_to_message_id
            msg["References"] = reply_to_message_id

        msg.attach(MIMEText(body_html, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        payload: dict = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        return payload

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
    ) -> dict:
        """
        Send a new email.

        :param to: Recipient email address.
        :param subject: Email subject.
        :param body_html: HTML body content.
        :return: Sent message resource from Gmail API.
        """
        service = self._service_client()
        message = self._build_message(to=to, subject=subject, body_html=body_html)
        try:
            sent = service.users().messages().send(userId="me", body=message).execute()
            return sent
        except HttpError as e:
            raise RuntimeError(f"Gmail API error: {e.status_code} — {e.error_details}") from e

    def send_reply(
        self,
        to: str,
        subject: str,
        body_html: str,
        reply_to_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        """
        Send a reply email, optionally continuing a Gmail thread.

        :param to: Recipient email address.
        :param subject: Email subject (usually "Re: <original subject>").
        :param body_html: HTML body content.
        :param reply_to_message_id: The Message-ID header of the original email (for threading).
        :param thread_id: Gmail threadId to attach this reply to.
        :return: Sent message resource from Gmail API.
        """
        service = self._service_client()
        message = self._build_message(
            to=to,
            subject=subject,
            body_html=body_html,
            reply_to_message_id=reply_to_message_id,
            thread_id=thread_id,
        )
        try:
            sent = service.users().messages().send(userId="me", body=message).execute()
            return sent
        except HttpError as e:
            raise RuntimeError(f"Gmail API error: {e.status_code} — {e.error_details}") from e

            
gmail_helper = GmailHelper(
    credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "gmail_credentials.json"),
    token_path=os.getenv("GMAIL_TOKEN_PATH", "gmail_token.json"),
)
