from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


def env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def env_int(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Config:
    CONDA_PREFIX: str | None = getenv("CONDA_PREFIX", None)
    WEB_SOCKET_PORT: int = int(getenv("WEB_SOCKET_PORT", "3050"))
    # DB Config
    DB_USER: str | None = getenv("DB_USER", None)
    DB_PASS: str | None = getenv("DB_PASS", None)
    DB_PORT: int | None = int(getenv("DB_PORT", None)) if getenv("DB_PORT") else None
    DB_HOST: str | None = getenv("DB_HOST", None)

    ADSB_DB_NAME: str | None = getenv("ADSB_DB_NAME", None)
    AIS_DB_NAME: str | None = getenv("AIS_DB_NAME", None)
    FISHY_VESSELS_DB_NAME: str | None = getenv("FISHY_VESSELS_DB_NAME")
    FISHY_REPORTS_DB_NAME: str | None = getenv("FISHY_REPORTS_DB_NAME")
    
    # LLM Model Configuration (Hugging Face model ID and generation parameters)
    
    LLAMA_BACKEND_SOCKET: str = "http://127.0.0.1:8000/v1"
    MAX_AGENT_STEPS: int = 20
    INFERENCE_SERVER_URL: str = f"http://127.0.0.1:{getenv("INFERENCE_SERVER_PORT", "8000")}/v1"
    
config = Config()