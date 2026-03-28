# Tema 3 - Construirea unor teste unitare și adăugarea de metrici relevante în evaluarea modelului

## Descriere

În această temă, extindem agentul construit în Tema 2 ([Lectia3/Tema2/agent_montan.py](../../Lectia3/Tema2/agent_montan.py)) prin:

- Adăugarea de endpoint-uri API folosind frameworkul **FastAPI**;
- Rularea endpoint-urilor FastAPI pe un server local cu **Uvicorn**;
- Testarea endpoint-urilor modelului deployat;
- Evaluarea modelului folosind **DeepEval** (bibliotecă folosită pentru abordarea LLM-as-a-Judge).

## Resurse

Putem folosi ca resurse urmatoarele fisiere din repo-ul de teme:
   - [tema_3_tests/test_main.py](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/tema_3_tests/test_main.py)
   - [tema_3_evaluation/evaluate.py](https://github.com/dragosbajenaru1001/Teme_pentru_acasa/blob/main/tema_3_evaluation/evaluate.py)

## Structura temei

Pentru organizarea folderelor, rolul fiecarui fisier si diagrama componentelor,
consulta documentul dedicat:

- [STRUCTURA_TEMA3.md](STRUCTURA_TEMA3.md)
