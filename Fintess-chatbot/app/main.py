from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# reduce TensorFlow log noise in server output
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
logging.getLogger("tensorflow").setLevel(logging.ERROR)

from src.services.fitness_assistant import FitnessAssistant

from pydantic import BaseModel
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

@asynccontextmanager
async def lifespan(app: FastAPI):    
    load_dotenv()
    yield