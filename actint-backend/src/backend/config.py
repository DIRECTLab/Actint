from dotenv import load_dotenv
from os import getenv
from dataclasses import dataclass

# Searches for .env in progressively higher directories until it finds it
load_dotenv()

@dataclass(frozen=True)
class Config:
    CONDA_PREFIX: str | None = getenv("CONDA_PREFIX", None)
    WEB_SOCKET_PORT: int = int(getenv("WEB_SOCKET_PORT", "3050"))
    # DB Config
    DB_HOST: str | None = getenv("DB_HOST", None)
    ADSB_DB_NAME: str | None = getenv("ADSB_DB_NAME", None)
    AIS_DB_NAME: str | None = getenv("AIS_DB_NAME", None)
    DB_USER: str | None = getenv("DB_USER", None)
    DB_PASS: str | None = getenv("DB_PASS", None)
    DB_PORT: int | None = int(getenv("DB_PORT", None)) if getenv("DB_PORT") else None
    MODEL_ID: str | None = getenv("MODEL_ID", None)

    MAX_AGENT_STEPS: int = 20
    INFERENCE_SERVER_URL: str = f"http://127.0.0.1:{getenv("INFERENCE_SERVER_PORT", "8000")}/v1"
    
config = Config()