# Tema 3 - Construirea unor teste unitare și adăugarea de metrici relevante în evaluarea modelului

## Descriere

- Implementați teste unitare pentru funcționalitatea principală a modelului.
- Adăugați metrici relevante pentru evaluare (ex: acuratețe, precizie, recall, F1, etc.).
- Asigurați reproducibilitate și claritatea raportului de testare.

## Cerințe

1. Fork din repository:
   - [Teme pentru acasă](https://github.com/dragosbajenaru1001/Teme_pentru_acasa)

2. Rezolvați cerințele din fișierele de referință:
   - [tema_3_tests/test_main.py](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/tema_3_tests/test_main.py)
   - [tema_3_evaluation/evaluate.py](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/tema_3_evaluation/evaluate.py)


## Instructiuni:

- Rulați în terminal: python -m venv venv . .\venv\Scripts\activate pip install -r .\requirements.txt

- Redenumiți fișierul .env.sample în .env și completați variabilele cu valorile dvs.

- Testare: python src/tema_2_services/service.py

- Pentru a rula testele din test_main rulați: în primul terminal: uvicorn app.main:app --reload și în al doilea terminal: pytest

- Pentru a rula metricile din evaluate rulați: în primul terminal: uvicorn app.main:app --reload și în al doilea terminal: python -m tema_3_evaluation.evaluate