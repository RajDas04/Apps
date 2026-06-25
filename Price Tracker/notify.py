from email.mime.text import MIMEText
from config import settings
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def _get_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=settings.email_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.email_cli_id,
        client_secret=settings.email_cli_secret,
    )
    creds.refresh(Request())  # auto-refreshes the access token
    return build("gmail", "v1", credentials=creds)


def _send(to_email: str, subject: str, body: str):
    service = _get_gmail_service()
    msg = MIMEText(body)
    msg["To"] = to_email
    msg["From"] = settings.email_from
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def send_email(to_email: str, product_name: str, current_price: int, previous_price: int, drop_amount: int):
    try:
        body = f"""
        Yo! The product you're tracking has dropped price.

        =============================
        Product :   {product_name}

        Current Price : ₹ {current_price}

        Previous Price : ₹ {previous_price}
        =============================

        That's ₹ {drop_amount} drop, it's {round(drop_amount / previous_price * 100, 1)}% less than the past price.

        Regards,
        Price Tracker.
        """
        _send(to_email, "Price Drop Alert, Price Tracker", body)

    except Exception as e:
        print(f"Email Failed: {e}")
        raise


def send_otp(to_email: str, otp: str):
    try:
        body = f"""
        One Time Password (OTP) is: {otp}

        This OTP is valid for 10 minutes.

        ** If you did not request this, please ignore this email. **

        Regards,
        Price Tracker.
        """
        _send(to_email, "OTP for Price Tracker", body)

    except Exception as e:
        print(f"OTP Email Failed: {e}")
        raise

if __name__ == "__main__":
    send_otp("debjit826@gmail.com", "123456")