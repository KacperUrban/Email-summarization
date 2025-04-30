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
import chromadb

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
    """Fetch emails from specified senders within a time range using the Gmail API.

    Args:
        service: Gmail API client.
        emails (list[str]): List of sender email addresses.
        max_results (int): Max number of emails to retrieve.
        timedelta_days (int): How many days back to look for emails.

    Returns:
        list[dict]: Cleaned email contents including subject, sender, and body.
    """
    # Get emails from the past `timedelta_days` days
    date_7_days = datetime.now() - timedelta(days=timedelta_days)
    query = f"from:({' OR '.join(emails)}) after:{date_7_days.strftime('%Y/%m/%d')}"
    
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
        date_raw = next((h["value"] for h in headers if h["name"] == "Date"), "")

        try:
            date_obj = datetime.strptime(date_raw, "%a, %d %b %Y %H:%M:%S %z")
            formatted_date = date_obj.strftime("%d:%m:%Y")
        except ValueError:
            formatted_date = datetime.now().strftime("%d:%m:%Y")

        body = ""
        plain_text_body = ""
        html_body = ""
        plain_text_found = False
        html_found = False
        
        parts = payload.get("parts", [])

        if parts:
            for part in parts:
                mime_type = part.get("mimeType", "")
                data = part.get("body", {}).get("data")
                if not data:
                    continue

                decoded_data = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8")

                if mime_type == "text/html":
                    html_body = decoded_data
                    html_found = True

                elif mime_type == "text/plain":
                    plain_text_body = decoded_data
                    plain_text_found = True

        else:
            # No parts – body is directly available
            data = payload.get("body", {}).get("data")
            if data:
                decoded_data = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8")
                if "<html>" in decoded_data.lower():
                    html_body = decoded_data
                    html_found = True
                else:
                    plain_text_body = decoded_data
                    plain_text_found = True

        # Choose best version to display
        if html_found:
            body = html_body
        elif plain_text_found:
            body = plain_text_body
        else:
            body = ""

        email_data.append({
            "id": msg["id"],
            "subject": subject,
            "from": sender,
            "body": clean_email_text(extract_clean_text(body.strip())),
            "plain_text_available": plain_text_found,
            "html_available": html_found,
            "date": formatted_date,
        })

    return email_data


def updated_chromadb(emails: list[dict]) -> None:
    """This function add new documents to chromadb only if emails have a different messages ids
    (avoid duplication). For that collect existed ids from db and remove any email with the same
    ids.

    Args:
        emails (list[dict]): list of dicts, which describe emails entites (body, subject etc.)
    """
    ids = [email["id"] for email in emails]
    
    chroma_client = chromadb.PersistentClient(path="./chromadb")
    collection = chroma_client.get_or_create_collection(name="emails")
    existing_ids = collection.get(ids=ids, include=[])
    existing_ids_set = set(existing_ids['ids'])
    new_emails = [email for email in emails if email["id"] not in existing_ids_set]

    
    if new_emails:
        collection.add(
            documents=[email["body"] for email in new_emails],
            ids=[email["id"] for email in new_emails],
            metadatas=[{"subject": email["subject"], "from": email["from"], "date": email["date"]} for email in new_emails]
        )
        print("Database was updated!")
    else:
        print("Database was not updated! Nothing new :(")

if __name__ == "__main__":
    load_dotenv()
    service = authenticate_gmail()
    emails = os.getenv("EMAIL_LIST").split(",")

    emails = get_emails(service, emails)
    updated_chromadb(emails)
