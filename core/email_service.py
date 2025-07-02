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

logger = logging.getLogger(__name__)

def send_otp(recipient_email, username, otp_code):
    try:
        logger.info(f"Attempting to send OTP email to {recipient_email}")

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

        logger.info(f"OTP email sent successfully to {recipient_email}")

        return {"success": True, "message": "OTP email sent successfully"}

    except Exception as e:
        logger.error(f"Error sending OTP email to {recipient_email}: {str(e)}")
        return {"success": False, "error": str(e)}

def send_status_change_email(recipient_email, username, new_status):
    """Send an email to the user when their account status changes to restricted, suspended, or banned."""
    try:
        logger.info(f"Attempting to send status change email to {recipient_email}")
        status_messages = {
            'RESTRICTED': {
                'subject': 'Your CTF Account Has Been Restricted',
                'body': f"""
                <p>Dear <strong>{username}</strong>,</p>
                <p>Your account status has been changed to <b>RESTRICTED</b>. Some features may be limited. If you believe this is a mistake, please contact support.</p>
                """
            },
            'SUSPENDED': {
                'subject': 'Your CTF Account Has Been Suspended',
                'body': f"""
                <p>Dear <strong>{username}</strong>,</p>
                <p>Your account has been <b>SUSPENDED</b>. You cannot log in or participate until further notice. Contact support for more information.</p>
                """
            },
            'BANNED': {
                'subject': 'Your CTF Account Has Been Banned',
                'body': f"""
                <p>Dear <strong>{username}</strong>,</p>
                <p>Your account has been <b>BANNED</b> due to violations of our terms of service. If you believe this is an error, please contact support.</p>
                """
            }
        }
        status_key = new_status.upper()
        if status_key not in status_messages:
            logger.warning(f"No email template for status: {new_status}")
            return {"success": False, "error": "No template for this status."}
        html_content = f"""
        <!DOCTYPE html>
        <html><head><meta charset='utf-8'><title>Account Status Update</title></head><body>
        <div style='max-width:600px;margin:40px auto;background:#fff;border:1px solid #ddd;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.05);padding:30px;'>
        <div style='text-align:center;border-bottom:1px solid #e0e0e0;margin-bottom:20px;'><h1>CTF Platform Notification</h1></div>
        {status_messages[status_key]['body']}
        <div style='font-size:12px;text-align:center;color:#999;border-top:1px solid #e0e0e0;margin-top:30px;padding-top:15px;'>&copy; {str(time.localtime().tm_year)} CTF Platform. All rights reserved.</div>
        </div></body></html>
        """
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            msg = MIMEMultipart()
            msg['From'] = f"ctflogin <{MAIL_DEFAULT_SENDER}>"
            msg['To'] = recipient_email
            msg['Subject'] = status_messages[status_key]['subject']
            msg.attach(MIMEText(html_content, 'html'))
            server.sendmail(MAIL_DEFAULT_SENDER, recipient_email, msg.as_string())
        logger.info(f"Status change email sent successfully to {recipient_email}")
        return {"success": True, "message": "Status change email sent successfully"}
    except Exception as e:
        logger.error(f"Error sending status change email to {recipient_email}: {str(e)}")
        return {"success": False, "error": str(e)}
                

def send_status_restored_email(recipient_email, username):
    """Send an email to the user when their account status is restored to ACTIVE from a restricted state."""
    try:
        logger.info(f"Attempting to send status restored email to {recipient_email}")
        subject = 'Your CTF Account Has Been Restored'
        body = f"""
        <p>Dear <strong>{username}</strong>,</p>
        <p>We are pleased to inform you that your account status has been restored to <b>ACTIVE</b>. You now have full access to the platform again. Welcome back!</p>
        <p>If you have any questions or need assistance, feel free to contact our support team.</p>
        """
        html_content = f"""
        <!DOCTYPE html>
        <html><head><meta charset='utf-8'><title>Account Status Restored</title></head><body>
        <div style='max-width:600px;margin:40px auto;background:#fff;border:1px solid #ddd;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.05);padding:30px;'>
        <div style='text-align:center;border-bottom:1px solid #e0e0e0;margin-bottom:20px;'><h1>CTF Platform Notification</h1></div>
        {body}
        <div style='font-size:12px;text-align:center;color:#999;border-top:1px solid #e0e0e0;margin-top:30px;padding-top:15px;'>&copy; {str(time.localtime().tm_year)} CTF Platform. All rights reserved.</div>
        </div></body></html>
        """
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            msg = MIMEMultipart()
            msg['From'] = f"ctflogin <{MAIL_DEFAULT_SENDER}>"
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))
            server.sendmail(MAIL_DEFAULT_SENDER, recipient_email, msg.as_string())
        logger.info(f"Status restored email sent successfully to {recipient_email}")
        return {"success": True, "message": "Status restored email sent successfully"}
    except Exception as e:
        logger.error(f"Error sending status restored email to {recipient_email}: {str(e)}")
        return {"success": False, "error": str(e)}