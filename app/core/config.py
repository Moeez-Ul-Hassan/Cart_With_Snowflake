from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise Cart API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Updated for PostgreSQL
    DATABASE_URL: str = "postgresql+psycopg2://postgres:enterprise_password@localhost:5432/cart_db"
    REDIS_URL: str = "redis://localhost:6379/0" 

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()