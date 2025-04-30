import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import time 

# Load environment variables (e.g., MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER)
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

# SMTP configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def send_otp(recipient_email, username, otp_code):
    try:
        logging.info(f"Attempting to send OTP email to {recipient_email}")

        # Create the HTML content for the email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Authentication Code</title>
          <style>
            body {{
              font-family: 'Roboto Mono', monospace;
              background-color: #f4f4f4;
              color: #333;
              margin: 0;
              padding: 0;
            }}
            .container {{
              max-width: 600px;
              margin: 40px auto;
              background-color: #ffffff;
              border: 1px solid #dddddd;
              border-radius: 8px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.05);
              padding: 30px;
            }}
            .header {{
              text-align: center;
              border-bottom: 1px solid #e0e0e0;
              margin-bottom: 20px;
            }}
            .header h1 {{
              margin: 0;
              font-size: 20px;
              color: #1a1a1a;
            }}
            .content {{
              font-size: 15px;
              line-height: 1.6;
            }}
            .otp-code {{
              font-size: 28px;
              letter-spacing: 6px;
              text-align: center;
              margin: 30px 0;
              background-color: #f0f0f0;
              padding: 15px 20px;
              border-radius: 6px;
              border: 1px solid #ccc;
              color: #000;
            }}
            .footer {{
              font-size: 12px;
              text-align: center;
              color: #999;
              border-top: 1px solid #e0e0e0;
              margin-top: 30px;
              padding-top: 15px;
            }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>CTF Platform Verification</h1>
            </div>
            <div class="content">
              <p>Dear <strong>{username}</strong>,</p>
              <p>Your one-time authentication code is:</p>
              <div class="otp-code">{otp_code}</div>
              <p>This code is valid for the next <strong>5 minutes</strong>.</p>
              <p>If you did not request this code, no further action is required.</p>
            </div>
            <div class="footer">
              &copy; {str(time.localtime().tm_year)} CTF Platform. All rights reserved.
            </div>
          </div>
        </body>
        </html>
        """

        # Establish connection to SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(MAIL_USERNAME, MAIL_PASSWORD)

            # Create the email message
            msg = MIMEMultipart()
            msg['From'] = f"ctflogin <{MAIL_DEFAULT_SENDER}>"
            msg['To'] = recipient_email
            msg['Subject'] = "Your Authentication Code for CTF Platform"

            # Attach the HTML content to the email
            msg.attach(MIMEText(html_content, 'html'))

            # Send the email
            server.sendmail(MAIL_DEFAULT_SENDER, recipient_email, msg.as_string())

        logging.info(f"OTP email sent successfully to {recipient_email}")

        return {"success": True, "message": "OTP email sent successfully"}

    except Exception as e:
        logging.error(f"Error sending OTP email to {recipient_email}: {str(e)}")
        return {"success": False, "error": str(e)}