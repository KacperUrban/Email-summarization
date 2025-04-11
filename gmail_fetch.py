import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_emails(
    service, emails: list[str], max_results: int = 100, timedelta_days: int = 7
) -> list[dict]:
    """This function get gmail API client and emails and some params. The create apprioriate query, transform messages and
    store information about emails.

    Args:
        service (_type_): gmail API client
        emails (list[str]): list of emails (in my example newsletters)
        max_results (int, optional): maximum number of emails fetched from your inbox. Defaults to 100.
        timedelta_days (int, optional): duration of time, which will be used to fetched emails. Defaults to 7.

    Returns:
        list[dict]: list of emails. This object will be presented as dictionaries. This entites will contains subject,
        email adrress and body of the message
    """
    date_7_days = datetime.now() - timedelta(days=timedelta_days)
    query = f"from:({' OR '.join(emails)}) after:{date_7_days.strftime("%Y/%m/%d")}"
    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
        payload = msg_data["payload"]
        headers = payload.get("headers", [])

        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "")

        body = ""
        parts = payload.get("parts", [])
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part["body"]["data"]
                html = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8")
                body = clean_email_text(extract_clean_text(html))
                break

        emails.append({"subject": subject, "from": sender, "body": body.strip()})

    return emails


if __name__ == "__main__":
    load_dotenv()
    service = authenticate_gmail()
    emails = os.getenv("EMAIL_LIST").split(",")

    emails = get_emails(service, emails)
    print(emails[-1]["body"])
