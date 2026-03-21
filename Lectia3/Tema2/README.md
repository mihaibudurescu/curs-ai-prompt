# Tema 2 - Construiți un asistent care să răspundă la informații relevante doar pentru ideea dumneavoastră.

## Cerinte

- Fork din github la repository-ul https://github.com/dragosbajenaru1001/Teme_pentru_acasa
- Rezolvati cerintele To-Do din fisierul https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/src/tema_2_services/service.py

---

## Instructiuni

### 1. Instalati Python 3.10.11 (o singura data)
https://www.python.org/downloads/release/python-31011/

### 2. Creati si activati virtualenv

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurati variabilele de mediu

Obtineti un API key gratuit Groq la: https://console.groq.com/

Creati un fisier `.env` in radacina repository-ului:

```
GROQ_API_KEY=your_groq_api_key_here
DATA_DIR=./data
```
In variabila WEB_URLS puneti paginile web pe care se va antrena modelul

```
WEB_URLS=https://turistmania.ro;https://sglm.ro;https://www.traseeromane.ro;https://edenhill.ro/trasee-montane/;https://www.descopera.ro/trasee-montane;https://www.salvamontromania.ro
TF_ENABLE_ONEDNN_OPTS=0
```
### 4. Rulare

```powershell
python agent_montan.py # nume_agent.py
```

> **Nota:** Prima rulare descarca si indexeaza toate URL-urile din `WEB_URLS` — poate dura cateva minute. Rulari ulterioare folosesc cache-ul din `data/`.

### 5. Resetare cache (dupa modificarea WEB_URLS sau trasee.json)

```powershell
Remove-Item -Force .\data\data_chunks.json, .\data\faiss.index, .\data\faiss.index.meta -ErrorAction SilentlyContinue
```


# Rezolvare
## Asistent Montan Romania — agent_montan.py

Un agent RAG (Retrieval-Augmented Generation) specializat in turismul montan din Romania. Raspunde doar la intrebari relevante despre trasee, cabane, varfuri si activitati in muntii romanesti, ignorand intrebarile din afara domeniului.

---

### Cum functioneaza

```
Intrebare utilizator
        │
        ▼
┌─────────────────────┐
│  Verificare         │  Embeddings (Universal Sentence Encoder)
│  relevanta          │  Similaritate cosine cu propozitia de referinta
└────────┬────────────┘
         │ irelevant → raspuns de respingere
         │ relevant
         ▼
┌──────────────────────────────────────────────────┐
│  Incarcare date din doua surse                   │
│                                                  │
│  1. Web scraping (WebBaseLoader + BeautifulSoup) │
│     URL-urile din WEB_URLS, chunked si cached    │
│                                                  │
│  2. JSON local (data/trasee.json)                │
│     409 trasee cu nume, localitate, dificultate, │
│     durata, distanta, denivelare, sursa_url      │
└────────┬─────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  Retrieval hibrid (doua strategii combinate)     │
│                                                  │
│  A. Exact match pe localitate_start / judet      │
│     Cuvintele din intrebare sunt curatate de     │
│     punctuatie si cautate direct in JSON         │
│                                                  │
│  B. Cautare semantica FAISS (top-15)             │
│     IndexFlatIP cu embeddings USE, cached pe     │
│     disc, rebuildit automat la schimbari         │
│                                                  │
│  Rezultatele A au prioritate, urmate de B        │
│  (deduplicate)                                   │
└────────┬─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│  LLM (Groq)         │  System prompt + context + intrebare → raspuns
│  llama-3.3-70b      │  Include sursa_url pentru fiecare traseu listat
└─────────────────────┘
```

---

### Structura proiectului

```
Tema2/
├── agent_montan.py     # Agentul principal
├── requirements.txt    # Dependinte Python
├── README.md
└── data/               # Date si cache
    ├── trasee.json          # 409 trasee montane (sursa locala)
    ├── data_chunks.json     # Cache chunks web + JSON (generat automat)
    ├── faiss.index          # Index FAISS (generat automat)
    └── faiss.index.meta     # Hash pentru invalidare cache (generat automat)
```

---

### Variabile de mediu

| Variabila | Descriere | Obligatorie |
|-----------|-----------|-------------|
| `GROQ_API_KEY` | API key pentru Groq LLM | Da |
| `DATA_DIR` | Director pentru cache FAISS, chunks si trasee.json | Nu (default: `/app/data`) |
| `WEB_URLS` | URL-uri separate prin `;` pentru scraping | Nu |
| `USE_MODEL_URL` | URL model Universal Sentence Encoder | Nu (are default) |
| `TF_ENABLE_ONEDNN_OPTS` | Dezactiveaza warning-uri TensorFlow | Nu |

---

### Exemple

```
Intrebare cu localitate:  "Care sunt circuitele montane din Busteni?"
Raspuns:                  Lista trasee cu dificultate, durata si sursa_url

Intrebare generala:       "Ce echipament am nevoie pentru Fagaras?"
Raspuns:                  Sfaturi echipament din contextul web scraped

Intrebare irelevanta:     "Care este reteta de sarmale?"
Raspuns:                  "Intrebarea ta nu pare a fi despre turismul montan..."
```

### Localitati cu cele mai multe trasee in date

| Localitate | Trasee |
|------------|--------|
| Cheia | 24 |
| Busteni | 30 |
| Azuga | 16 |
| Zarnesti | 14 |
| Balea Lac | 21 |
| Sinaia | 11 |



