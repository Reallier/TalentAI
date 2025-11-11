from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # Database
    database_url: str
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "talentai"
    database_user: str = "talentai"
    database_password: str = "talentai123"
    
    # DashScope/Qwen
    dashscope_api_key: str
    llm_model: str = "qwen-turbo"
    embedding_model: str = "text-embedding-v1"
    
    # Application
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    log_level: str = "INFO"
    
    # Ranking Weights
    weight_vector_sim: float = 0.5
    weight_lexical: float = 0.25
    weight_skill_coverage: float = 0.15
    weight_recency: float = 0.1
    
    # Recall Settings
    topk_lexical: int = 50
    topk_vector: int = 50
    topk_final: int = 20
    
    # Deduplication
    dedup_strong_match: str = "exact"
    dedup_weak_similarity: float = 0.85
    
    # Indexing
    embedding_version: int = 1
    index_delay_seconds: int = 5
    
    # Storage
    upload_dir: str = "/app/uploads"
    max_file_size_mb: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()