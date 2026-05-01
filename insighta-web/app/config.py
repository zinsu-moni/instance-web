import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    backend_url: str = os.getenv("BACKEND_URL", "https://hng-task-lemon.vercel.app").rstrip("/")
    frontend_url: str = os.getenv("FRONTEND_URL", "https://instance-web.vercel.app").rstrip("/")
    secret_key: str = os.getenv("SECRET_KEY", "your-random-secret-key-for-csrf")
    port: int = int(os.getenv("PORT", "5000"))

    @property
    def frontend_callback_url(self) -> str:
        return f"{self.frontend_url}/auth/callback"


settings = Settings()
