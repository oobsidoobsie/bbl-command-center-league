"""Send the reports by email through Gmail (SMTP + an app password stored only on this PC)."""
import os
import smtplib
from email.message import EmailMessage


def send(cfg, secret, subject, html_body, text_body, attachments=()):
    """cfg: dict from config.txt. secret: Gmail app password (from secret.txt). Returns True if sent."""
    user, to = cfg.get("gmail_address", ""), cfg.get("email_to", "")
    if not (user and to and secret):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text_body or "Open the HTML version of this email.")
    msg.add_alternative(html_body, subtype="html")
    for path in attachments:
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                msg.add_attachment(f.read(), maintype="image", subtype="png", filename=os.path.basename(path))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, secret.replace(" ", ""))
        s.send_message(msg)
    return True
