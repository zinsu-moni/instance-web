import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    backend_url: str = (os.getenv("BACKEND_URL") or "").rstrip("/")
    frontend_url: str = (os.getenv("FRONTEND_URL") or "").rstrip("/")
    secret_key: str = os.getenv("SECRET_KEY", "your-random-secret-key-for-csrf")
    port: int = int(os.getenv("PORT", "5000"))


settings = Settings()
