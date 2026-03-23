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


## Instructiuni

Rulati comenzile in ordinea de mai jos.

1. Creati mediul virtual (o singura data, la nivel de repository):

```powershell
python -m venv venv
```

2. Activati mediul virtual:

```powershell
.\venv\Scripts\activate
```

3. Instalati dependintele din `requirements.txt`:

```powershell
pip install -r .\requirements.txt
```

4. Redenumiti `.env.sample` in `.env` si completati variabilele necesare.

5. Testare rapida serviciu:

```powershell
python src/tema_2_services/service.py
```

6. Rulare teste unitare (`test_main.py`):

Terminal 1:

```powershell
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
pytest
```

7. Rulare metrici (`evaluate.py`):

Terminal 1:

```powershell
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
python -m tema_3_evaluation.evaluate
```

## Note importante

- In acest repository folosim un singur mediu virtual: `venv` din radacina proiectului.
- Puteti avea mai multe fisiere `requirements.txt` pe subfoldere, dar pachetele se instaleaza in interpreterul activ (acelasi `venv` daca este activat).
- Recomandat: folositi mereu `python -m pip install -r <cale_catre_requirements.txt>` ca sa evitati instalarea in alt interpreter.