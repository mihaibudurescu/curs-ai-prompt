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

### 1. Verificati intai ce interpretor python este activ, deoarece in locatia acestuia se vor crea resursele de mai jos

```powershell
python -c "import sys; print(sys.executable)"
```

### 2. Creati mediul virtual (o singura data, la nivel de repository):
> **Nota:** Daca a fost creat de la lectiile anterioare puteti da skip acestui pas

```powershell
python -m venv venv
```

### 3. Activati mediul virtual:

```powershell
.\venv\Scripts\activate
```

### 4. Instalati dependintele din `requirements.txt`:
> **Nota:** Puteti avea mai multe fisiere `requirements.txt` pe subfoldere, deci atentie la `cale_catre_requirements.txt`, desi pachetele se vor instala intr-o singura locatie (acelasi `venv` daca este activat).

```powershell
pip install -r .\requirements.txt
```

### 5. Creati un fisier .env care va contine variabilele necesare pentru aplicatii

### 6. Rulare aplicatiei Python

```powershell
python <cale_catre_aplicatie>.py
```

### 7. Rulare teste unitare (`test_main.py`):

Terminal 1:

```powershell
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
pytest
```

### 8. Rulare metrici (`evaluate.py`):

Terminal 1:

```powershell
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
python -m Lectia5\Tema3\evaluation\evaluate.py
```