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
    DB_HOST: str | None = getenv("DB_HOST", None)
    DB_NAME: str | None = getenv("DB_NAME", None)
    DB_USER: str | None = getenv("DB_USER", None)
    DB_PASS: str | None = getenv("DB_PASS", None)
    # DB_PORT is set to None if undefined, and errors if set to something that
    # can't be converted to an int
    DB_PORT: int | None = int(getenv("DB_PORT", None)) if getenv("DB_PORT") else None
    # LLM Model Configuration (Hugging Face model ID and generation parameters)
    MODEL_ID: str = getenv("MODEL_ID", "Qwen/Qwen3.5-2B")
    MAX_NEW_TOKENS: int = int(getenv("MAX_NEW_TOKENS", "4096"))
    
config = Config()