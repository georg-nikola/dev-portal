from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://devportal:devportal@localhost:5432/devportal"
    status_check_interval: int = 60  # seconds between background health checks
    status_check_timeout: int = 10   # seconds before a ping is considered failed

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
