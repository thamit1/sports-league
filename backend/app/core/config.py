from pydantic_settings import BaseSettings
from typing import List
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent  # project root


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET_KEY: str = "change-jwt-secret-too"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Set DB_TYPE=mysql in .env to switch to MySQL
    DB_TYPE: str = "sqlite"

    # SQLite (default - zero config)
    SQLITE_FILE: str = str(BASE_DIR / "slms.db")

    # MySQL (only used if DB_TYPE=mysql)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "slms_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    CORS_ORIGINS: List[str] = ["http://localhost:8000"]

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "mysql":
            return (
                f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        # SQLite — file sits at project root as slms.db
        return f"sqlite:///{self.SQLITE_FILE}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
