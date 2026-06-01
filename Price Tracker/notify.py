import smtplib
from email.mime.text import MIMEText
from config import settings
from fastapi import HTTPException

def send_email(to_email: str, product_name: str, current_price: int, previous_price: int, drop_amount: int):
    try:
        subject = "Price Drop Alert, Price Tracker"
        body = f"""
        Yo! The product you're tracking has dropped price.

        =============================
        Product :   {product_name}
        

        Current Price : ₹ {current_price}

        Previous Price : ₹ {previous_price}
        =============================

        That's ₹ {drop_amount} drop, it's {round(drop_amount/previous_price * 100, 1)}% less than the past price.


        regards,
        Price Tracker.
        """
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.email_from, settings.email_password)
            server.sendmail(settings.email_from, to_email, msg.as_string())
    
    except Exception as e:
        print(f"Email Failed: {e}")
        raise

def send_otp(to_email: str, otp: str):
    try:
        subject = "OTP for Price Tracker"
        body = f"""
        One Time Password (OTP) is: {otp}

        This OTP is valid for 10 minutes.

        ** If you did not request this, please ignore this email. **

        Regards,
        Price Tracker.
        """
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.email_from, settings.email_password)
            server.sendmail(settings.email_from, to_email, msg.as_string())
    
    except Exception as e:
        print(f"OTP Email Failed: {e}")
        raise

# if __name__ == "__main__":
#     try:
#         send_email(to_email="PUTTHEEMAILHERE", product_name="Test Product", current_price=999, threshold=1000)
#     except Exception as e:
#         print(f"Failed to send test email: {e}")