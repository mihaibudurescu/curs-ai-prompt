# Tema 3 - Construirea unor teste unitare și adăugarea de metrici relevante în evaluarea modelului

## Descriere

În această temă, extindem agentul construit în Tema 2 ([Lectia3/Tema2/agent_montan.py](../../Lectia3/Tema2/agent_montan.py)) prin:

- Adăugarea de endpoint-uri API folosind frameworkul **FastAPI**;
- Rularea endpoint-urilor FastAPI pe un server local cu **Uvicorn**;
- Testarea endpoint-urilor modelului deployat;
- Evaluarea modelului folosind **DeepEval** (bibliotecă folosită pentru abordarea LLM-as-a-Judge).

## Resurse

Ca resurse putem sa copiem fisierele din locatiile de mai jos in repo-ul propriu:
   - [main.py](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/app/main.py)
   - [tema_3_tests](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/tema_3_tests)
   - [tema_3_evaluation](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/tema_3_evaluation)

## Relatia dintre fisiere

## 1) Flux aplicatie (runtime)
1. Pornesti serverul din `main.py` cu `uvicorn`.
2. Endpoint-ul `POST /chat/` apeleaza `RAGAssistant.assistant_response(...)`.
3. Clientii (sau scripturile de test/evaluare) primesc raspuns JSON.

## 2) Flux teste unitare
1. `tests/test_main.py` trimite request-uri catre API-ul pornit din `main.py`.
2. Verifica status code + continut raspuns.
3. Semnaleaza regresii in comportamentul endpoint-urilor.

## 3) Flux evaluare calitativa
1. `evaluation/evaluate.py` trimite input-uri de evaluare catre `POST /chat/`.
2. Raspunsurile sunt scorate de metrici `GEval` folosind modelul din `groq_llm.py`.
3. `report.py` genereaza raport HTML cu scoruri si explicatii.

## Planul de rezolvare

Pentru organizarea folderelor, rolul fiecarui fisier si diagrama componentelor,
consulta documentul dedicat:

- [Plan_rezolvare.md](Plan_rezolvare.md)
