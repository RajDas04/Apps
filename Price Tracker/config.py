from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    scrape_url: str
    refresh_token_expire_days: int
    redis_url: str
    email_from: str
    email_password: str
    email_cli_id: str
    email_cli_secret: str
    email_refresh_token: str

    class Config:
        env_file = ".env"

settings = Settings()