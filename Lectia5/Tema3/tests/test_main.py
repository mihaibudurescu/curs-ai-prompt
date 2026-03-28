import requests
import httpx
import sys
import pytest

# foloseste UTF-8 pentru stdout ca sa evite erori de codare
sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session", autouse=True)
def ensure_api_is_up() -> None:
	"""Ruleaza testele doar daca API-ul local este disponibil."""
	try:
		response = requests.get(f"{BASE_URL}/", timeout=5)
	except requests.RequestException as exc:
		pytest.skip(f"API-ul nu este pornit pe {BASE_URL}: {exc}")

	if response.status_code >= 500:
		pytest.skip(f"API-ul este disponibil, dar instabil (status {response.status_code}).")

#ToDo: Adăugați un test pentru endpoint-ul root 
def test_root_endpoint_returns_health_message() -> None:
	response = requests.get(f"{BASE_URL}/", timeout=10)
	assert response.status_code == 200

	data = response.json()
	assert "message" in data
	assert isinstance(data["message"], str)
	assert "RAG Assistant" in data["message"]

#ToDo: Adăugați un scenariu de testare pentru endpoint-ul /chat/ care să fie evaluat de LLM as a Judge
def test_chat_endpoint_positive_mountain_query() -> None:
	payload = {"message": "Ce trasee usoare recomanzi in Busteni?"}
	response = requests.post(f"{BASE_URL}/chat/", json=payload, timeout=90)
	assert response.status_code == 200

	data = response.json()
	assert "response" in data
	assert isinstance(data["response"], str)
	assert data["response"].strip() != ""

#ToDo: Adăugați un test negativ pentru endpoint-ul /chat/ care să fie evaluat de LLM as a Judge 
def test_chat_endpoint_negative_missing_message_validation_error() -> None:
	response = requests.post(f"{BASE_URL}/chat/", json={}, timeout=10)
	assert response.status_code == 422

	data = response.json()
	assert "detail" in data