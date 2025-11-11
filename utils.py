import smtplib
from email.mime.text import MIMEText

def send_email(to_email, subject, message):
    from_email = "yourgmail@gmail.com"
    password = "your_app_password"  # Gmail App password

    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(from_email, password)
        server.send_message(msg)
