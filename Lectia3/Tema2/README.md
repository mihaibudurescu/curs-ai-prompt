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
> Prima comanda creeaza folderul local `venv` in directorul curent,
> si un nou interpretor Python in `venv\Scripts\python.exe`.
> Daca exista deja, puteti sari peste acest pas.
>
> A doua comanda este necesara ca terminalul curent
> sa foloseasca interpreterul din `venv` (util cand aveti mai multe venv-uri),
> sau cand interpretorul este cel global (din AppData).
> Puteti iesi din `venv` cu `deactivate`.
>
> Puteti avea mai multe fisiere `requirements.txt` pe subfoldere,
> deci atentie la `cale_catre_requirements.txt`.
> Pachetele se vor instala intr-o singura locatie
> (acelasi `venv` daca este activat).

### 3. Instalati Ollama (local LLM, gratis, fara rate limits)

Descarcati si instalati Ollama de la: https://ollama.ai

```powershell
# Apoi rulati Ollama in background (intr-o alta fereastra terminal)
ollama serve

# In alta fereastra, descarcati un model (una singura data)
ollama pull mistral    # sau: llama2, neural-chat, etc.
```

### 4. Configurati variabilele de mediu

Creati un fisier `.env` in radacina repository-ului:

```
DATA_DIR=./data
```

### 4. (Optionale) Configurati URL-uri web pentru scraping

Daca vreti sa adaugati alte surse web, editati `.env`:

```
WEB_URLS=https://turistmania.ro;https://sglm.ro;https://www.traseeromane.ro;https://edenhill.ro/trasee-montane/;https://www.descopera.ro/trasee-montane;https://www.salvamontromania.ro
TF_ENABLE_ONEDNN_OPTS=0
```
### 5. Rulare

```powershell
# Asigura-te ca Ollama ruleaza in background (ollama serve in alta fereastra)
python agent_montan.py
```

> **Nota:** Prima rulare descarca si indexeaza toate URL-urile din `WEB_URLS` — poate dura cateva minute. Rulari ulterioare folosesc cache-ul din `data/`.

### 6. Resetare cache (dupa modificarea WEB_URLS sau trasee.json)

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
┌─────────────────────────────────────────────┐
│  Verificare relevanta (2 metode)            │  
│                                             │
│  1. Semantica: Embeddings (USE model)       │  
│     Similaritate cosine cu referinta        │
│                                             │
│  2. Lexicala: Keywords domeniu montan       │
│     "traseu", "munte", "bucegi", etc.       │
└────────┬────────────────────────────────────┘
         │ irelevant → raspuns de respingere
         │ relevant
         ▼
┌─────────────────────────────────────────────────────┐
│  Detectie zona montana (daca se mentioneaza)        │
│                                                     │
│  Daca intrebarea vizeaza o zona cunoscuta           │
│  (Bucegi, Fagaras, Ceahlau, etc.):                  │
│  → Incarca dinamica pagina Turistmania dedicata     │
│  → Raspuns structurat cu date zone-specifice        │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│  Incarcare date din doua surse                       │
│                                                      │
│  1. Web scraping (WebBaseLoader + BeautifulSoup)     │
│     URL-urile din WEB_URLS, chunked si cached        │
│                                                      │
│  2. JSON local (data/trasee.json)                    │
│     409 trasee cu nume, localitate, dificultate,     │
│     durata, distanta, denivelare, sursa_url          │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│  Retrieval hibrid (3 strategii)                      │
│                                                      │
│  A. Exact match pe localitate_start / judet          │
│     Cuvintele din intrebare cautate direct in JSON   │
│                                                      │
│  B. Cautare semantica FAISS (top-15)                 │
│     IndexFlatIP cu embeddings USE, cache pe disc     │
│                                                      │
│  C. Zone-specific retrieval                          │
│     Trasee relevante pentru zona detectata           │
│                                                      │
│  Rezultate: A + B combinate, deduplicate             │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  LLM (configurable)                      │  
│                                          │  
│  Optiuni:                                │
│  • Ollama (local, gratis) [RECOMANDAT]   │
│  • Groq (cloud, cu rate limit)           │
│  • Anthropic Claude                      │
│  • Soon: alti provideri                  │
│                                          │
│  System prompt + context + intrebare     │
│  → raspuns cu surse (sursa_url)          │
└──────────────────────────────────────────┘
```

**Nota:** Agentul suporta acum provider-e LLM pluggable. Pentru a evita rate limitele, se recomanda **Ollama** (local, gratis, fara API keys).

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

| Variabila | Descriere | Obligatorie | Note |
|-----------|-----------|-------------|-------|
| `DATA_DIR` | Director pentru cache FAISS, chunks si trasee.json | Nu (default: `/app/data`) | - |
| `WEB_URLS` | URL-uri separate prin `;` pentru scraping | Nu | Setare optionala in `.env` |
| `USE_MODEL_URL` | URL model Universal Sentence Encoder | Nu | Are default Google USE |
| `TF_ENABLE_ONEDNN_OPTS` | Dezactiveaza warning-uri TensorFlow | Nu | Setati la 0 daca vreti sa ascundeti warning-uri |

**Nota:** Nu mai aveti nevoie de `GROQ_API_KEY`. Ollama ruleaza local!

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



