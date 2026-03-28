from fastapi import FastAPI, HTTPException
import os
import logging
import importlib.util
from pathlib import Path

# reduce TensorFlow log noise in server output
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
logging.getLogger("tensorflow").setLevel(logging.ERROR)

TEMA3_DIR = Path(__file__).resolve().parent
TEMA2_DIR = TEMA3_DIR.parents[1] / "Lectia3" / "Tema2"
AGENT_MONTAN_PATH = TEMA2_DIR / "agent_montan.py"

if not AGENT_MONTAN_PATH.exists():
    raise FileNotFoundError(f"Nu gasesc agentul montan la: {AGENT_MONTAN_PATH}")

spec = importlib.util.spec_from_file_location("agent_montan", AGENT_MONTAN_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Nu pot incarca modulul din: {AGENT_MONTAN_PATH}")

agent_montan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_montan)
RAGAssistant = agent_montan.RAGAssistant

from pydantic import BaseModel
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

@asynccontextmanager
async def lifespan(app: FastAPI):    
    load_dotenv()
    yield

app = FastAPI(lifespan=lifespan)

# instanta chatbotului RAGAssistant
assistant_instance = RAGAssistant()

@app.get("/")
async def root():    
    return {"message": "Salut, RAG Assistant ruleaza!"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat/")
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat:
    Trimite mesajul catre RAGAssistant.assistant_response()
    si returneaza raspunsul.
    """
    try:
        # ruleaza metoda blocanta intr-un thread separat
        response = await asyncio.wait_for(
            asyncio.to_thread(assistant_instance.assistant_response, request.message),
            timeout=45
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Raspunsul de chat a expirat")
    except Exception as e:
        logging.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Chat esuat: {repr(e)}")

    return {"response": response}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
