Pentru a rula script-ul de ReAct, rulati urmatoarele comenzi in terminalul Powershell:
# creaza un virtual environment
python -m venv venv

# activeaza viatual envronment-ul
. .\venv\Scripts\activate

# instaleaza requirements
pip install -r .\requirements.txt

Redenumiti .env.sample in .env si cautati keys pe:
https://groq.com/
https://serper.dev/

Scriptul se ruleaza in terminalul Powershell cu:
python .\main.py