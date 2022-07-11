import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class Email:
    def __init__(self, email):
        self.email = email
        self.sender_email = os.environ.get("EMAIL_SENDER")
        self.password = os.environ.get("EMAIL_PASSWORD")

    def valid_email(self):
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        if re.fullmatch(regex, self.email):
            return True
        else:
            return False

    async def send_email(self, subject, body):
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.email
        message["Subject"] = subject

        message.attach(MIMEText(body, "plain"))

        text = message.as_string()

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context) as server:
            server.login(self.sender_email, self.password)
            server.sendmail(self.sender_email, self.email, text)
