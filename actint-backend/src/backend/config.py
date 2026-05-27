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

    WEB_SOCKET_PORT: int | None = env_int("WEB_SOCKET_PORT", 3050)

    DB_HOST: str | None = env_str("DB_HOST")
    ADSB_DB_NAME: str | None = env_str("ADSB_DB_NAME")
    AIS_DB_NAME: str | None = env_str("AIS_DB_NAME")
    FISHY_VESSELS_DB_NAME: str | None = env_str("FISHY_VESSELS_DB_NAME")
    FISHY_REPORTS_DB_NAME: str | None = env_str("FISHY_REPORTS_DB_NAME")
    DB_USER: str | None = env_str("DB_USER")
    DB_PASS: str | None = env_str("DB_PASS")
    DB_PORT: int | None = env_int("DB_PORT")

    MODEL_ID: str | None = env_str("MODEL_ID")
    MAX_NEW_TOKENS: int | None = env_int("MAX_NEW_TOKENS", 2048)

    MAX_AGENT_STEPS: int | None = env_int("MAX_AGENT_STEPS", 20)

    INFERENCE_SERVER_PORT: int | None = env_int("INFERENCE_SERVER_PORT", 8000)
    INFERENCE_SERVER_HOST: str | None = env_str("INFERENCE_SERVER_HOST", "127.0.0.1")
    INFERENCE_SERVER_URL: str = f"http://{INFERENCE_SERVER_HOST}:{INFERENCE_SERVER_PORT}/v1"


config = Config()