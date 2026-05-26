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
    # LLM Model Configuration (Hugging Face model ID and generation parameters)
    
    LLAMA_BACKEND_SOCKET: str = "http://127.0.0.1:8000/v1"
    MAX_AGENT_STEPS: int = 20



    # Edit and run the following command to start the local llamacpp LLM openAI server
"""
    ./llama-server \
     -m /scratch/username/chat_gpt/gpt-oss-120b-UD-Q8_K_XL-00001-of-00002.gguf # or enter the file path of where your model is located. \
     -c 131072 # This is the maximum context size \
     --host 0.0.0.0 # The address where your server is hosted\
     --port 8000 # Port number \
     -n 600 # Maximum new tokens to generate, this way it will not get stuck doing something that will infinitely generate tokens.
"""
    
config = Config()