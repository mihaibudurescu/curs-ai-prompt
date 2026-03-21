import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain_groq import ChatGroq
from config.settings import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT

llm = ChatGroq(model="llama-3.1-8b-instant")


def analyze_bugs(state):

    bugs = state["bugs"]

    prompt = f"""
You are a senior Python bug solver assistant.

Bugs found in the codebase are as follows (explained with #BUG tags in the code):
{bugs}

Explain:
- How to solve the bugs in the codebase, and what the potential issues are if they are not solved.
"""

    response = llm.invoke(prompt)

    text = response.content

    return {
        "analysis": text
    }


def send_email_node(state):

    analysis = state["analysis"]

    subject = "AI Bugs Report"
    body = f"""Automated Bugs Report

AI Analysis:
{analysis}
"""

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

    return {"email_status": f"Email sent to {EMAIL_RECIPIENT}"}