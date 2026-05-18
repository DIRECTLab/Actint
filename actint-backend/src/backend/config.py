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
    CONDA_PREFIX: str | None = getenv("CONDA_PREFIX")
    WEB_SOCKET_PORT: int = int(getenv("WEB_SOCKET_PORT", "3050"))
    DB_HOST: str | None = getenv("DB_HOST")
    DB_NAME: str | None = getenv("DB_NAME")
    DB_USER: str | None = getenv("DB_USER")
    DB_PASS: str | None = getenv("DB_PASS")
    # DB_PORT is set to None if undefined, and errors if set to something that
    # can't be converted to an int
    DB_PORT: int | None = int(getenv("DB_PORT")) if getenv("DB_PORT") else None
    
config = Config()