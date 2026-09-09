import smtplib
import os
from dotenv import load_dotenv
from email.message import EmailMessage

load_dotenv()

def send_email(to_email, subject, body):
    msg= EmailMessage()
    msg["Subject"]= subject
    msg["From"]= os.getenv("EMAIL_ADDRESS")
    msg["To"]= to_email

    msg.set_content(body)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_APP_PASSWORD"))
        server.send_message(msg)
