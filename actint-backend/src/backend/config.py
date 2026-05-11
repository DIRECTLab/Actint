from dotenv import load_dotenv
from os import getenv
from dataclasses import dataclass

# Searches for .env in progressively higher directories until it finds it
load_dotenv()

@dataclass(frozen=True)
class Config:
    CONDA_PREFIX: str | None = getenv("CONDA_PREFIX")
    WEB_SOCKET_PORT: int = int(getenv("WEB_SOCKET_PORT", "3050"))
    DB_HOST: str | None = getenv("DB_HOST")
    DB_NAME: str | None = getenv("DB_NAME")
    DB_USER: str | None = getenv("DB_USER")
    DB_PASS: str | None = getenv("DB_PASS")
    # DB_PORT is set to None if undefined, and errors if set to something that
    # can't be converted to an int
    DB_PORT: int | None = int(getenv("DB_PORT")) if getenv("DB_PORT") else None

    MAX_AGENT_STEPS: int = 20
    
config = Config()