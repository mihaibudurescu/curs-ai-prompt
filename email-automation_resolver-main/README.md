# langgraph-email-automation_resolver

Instrucțiuni:

1. Rulați în terminal:
python -m venv venv
. .\venv\Scripts\activate
pip install -r .\requirements.txt

2. Redenumiți fișierul .env.sample în .env și completați variabilele cu valorile dvs.

Pași pentru a genera parola de Gmail:
------------------------------------------------------------------------------------------
Enable 2-Factor Authentication on your Google account at myaccount.google.com/security

Generate an App Password:

Go to myaccount.google.com/apppasswords
Select app: "Mail", device: "Other" (name it anything, e.g. "Python")
Copy the 16-character password generated
Update your .env file:
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx   ← the 16-char app password (spaces ok or remove them)
------------------------------------------------------------------------------------------
