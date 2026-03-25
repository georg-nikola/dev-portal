from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://devportal:devportal@localhost:5432/devportal"
    status_check_interval: int = 60  # seconds between background health checks
    status_check_timeout: int = 10   # seconds before a ping is considered failed

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_not_be_default(cls, v: str) -> str:
        if v == "change-me-in-production":
            raise ValueError("JWT_SECRET must be set — do not use the default placeholder")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
