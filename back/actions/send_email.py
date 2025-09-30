import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

def send_project_ready_email(recipient_email: str, project_name: str):
    sender_email = "contact@nextraction.io"
    sender_name = "Nextraction Team"
    sender_password = os.getenv("ZOHO_PASSWORD")
    smtp_server = "smtp.zoho.com"
    smtp_port = 465  # SSL port recommended by Zoho

    if not sender_password:
        print("Error: ZOHO_PASSWORD not found in environment variables.")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = Header(f"Your Nextraction Project “{project_name}” Is Ready!", "utf-8")
    message["From"] = formataddr((str(Header(sender_name, "utf-8")), sender_email))
    message["To"] = recipient_email

    text = f"""Hello,

Your project "{project_name}" has been successfully analyzed and is ready for you to explore.

Visit your project dashboard:
https://nextraction.io/dashboard

Thank you for choosing Nextraction!

Best regards,
{sender_name}
"""
    html = f"""<html>
  <body style="font-family:Arial,sans-serif; color:#333; line-height:1.4;">
    <p>Hello,</p>
    <p>Your project <strong>“{project_name}”</strong> has been successfully analyzed and is now ready for you to explore.</p>
    <p><a href="https://nextraction.io/dashboard"
        style="background-color:#007BFF; color:white; padding:12px 20px;
               text-decoration:none; border-radius:4px;
               display:inline-block; font-size:16px;">
         View Your Dashboard
    </a></p>
    <p>Thank you for choosing Nextraction.</p>
    <p>Best regards,<br>{sender_name}</p>
  </body>
</html>"""

    message.attach(MIMEText(text, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        print(f"✅ Email sent successfully to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
