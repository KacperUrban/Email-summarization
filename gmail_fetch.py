import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
from dotenv import load_dotenv
import html2text
from datetime import datetime, timedelta
import re

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def extract_clean_text(html: str) -> str:
    """This function cleans html texts. Remove any HTML tags. You can setup if you want to ignore links and images.

    Args:
        html (str): raw html content from email

    Returns:
        str: preprocessed text, without HTML tags
    """

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    return h.handle(html).strip()


def clean_email_text(text: str) -> str:
    """This function clean text from any irrelevant characters. I remove hypensys and pipes strucutre like this: |--|-- etc.
    Then remove any pipes and blank lines. Last regex remove hypensys structured one by one i.e. ----.

    Args:
        text (str): raw text (in my example after html tags removal)

    Returns:
        str: preprocessed text
    """
    text = re.sub(r"[-|]+\s*\n\s*[-|]+", "", text)
    text = re.sub(r"[|]", "", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = re.sub(r"^\s*-+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'[\u200b\u200c\u200d\uFEFF\u00ad]', '', text)
    text = re.split(r'(?=# REPO of the week)', text)[0]
    text = text.strip()
    return text


def authenticate_gmail():
    """This function try to connect with gmail API, use token.json and credientals for autentication. If token not appear in
    project folder will be download from API.

    Returns:
        gmail_client: gmail client/service, which enables connection to API
    """
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("Refresh token expired or invalid. Deleting token.json and re-authenticating...")
                os.remove("token.json")
                return authenticate_gmail()
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_emails(
    service, emails: list[str], max_results: int = 100, timedelta_days: int = 7
) -> list[dict]:
    """This function retrieves emails from Gmail API and checks the available format (plain text or HTML)."""
    # Get emails from the past `timedelta_days` days
    date_7_days = datetime.now() - timedelta(days=timedelta_days)
    query = f"from:({' OR '.join(emails)}) after:{date_7_days.strftime('%Y/%m/%d')}"
    
    # Fetch email list using Gmail API
    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    
    messages = results.get("messages", [])
    email_data = []

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
        payload = msg_data["payload"]
        headers = payload.get("headers", [])

        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "")

        body = ""
        plain_text_found = False
        html_found = False
        
        parts = payload.get("parts", [])
        
        # Case 1: If parts are present (multipart email)
        if parts:
            for part in parts:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    data = part["body"]["data"]
                    body = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8")
                    plain_text_found = True
                    break
                
                if mime_type == "text/html":
                    data = part["body"]["data"]
                    body = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8")
                    html_found = True

        # Case 2: If no parts (single-part email, plain text or HTML directly in the body)
        if not parts:
            data = payload.get("body", {}).get("data")
            if data:
                body = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8")
                if "<html>" in body.lower():
                    html_found = True
                else:
                    plain_text_found = True

        # If no plain text found but HTML is found, fallback to HTML
        if not plain_text_found and html_found:
            body = body
        
        # Append the email data to the result list
        email_data.append({
            "subject": subject,
            "from": sender,
            "body": clean_email_text(extract_clean_text(body.strip())),
            "plain_text_available": plain_text_found,
            "html_available": html_found
        })

    return email_data


if __name__ == "__main__":
    load_dotenv()
    service = authenticate_gmail()
    emails = os.getenv("EMAIL_LIST").split(",")

    emails = get_emails(service, emails)
    documents = [email["body"] for email in emails]
    ids = [f"ids_{i + 1}" for i in range(len(emails))]

    for email in emails:
        print(email["body"])
