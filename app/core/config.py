from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""
    
    # Database settings
    DATABASE_URL: str = "postgresql://hyperliquid_user:hyperliquid_password@localhost:5432/hyperliquid_db"
    
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379"
    
    # Hyperliquid API settings
    HYPERLIQUID_API_URL: str = "https://api.hyperliquid.xyz/info"
    HYPERLIQUID_PRIVATE_KEY: Optional[str] = None
    HYPERLIQUID_WALLET_ADDRESS: Optional[str] = None
    
    # Popular coins to track (stored as string, accessed as list via property)
    POPULAR_COINS_STR: str = Field(default="BTC,ETH,SOL,AVAX,ARB,OP,MATIC", alias="POPULAR_COINS")
    
    # Task configuration settings
    BATCH_SIZE: int = Field(default=50, description="Number of traders to process per batch")
    WEBSOCKET_URL: str = Field(default="wss://api.hyperliquid.xyz/ws", description="Hyperliquid WebSocket URL")
    
    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379"
    
    # Application settings
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-this"
    
    model_config = {"env_file": ".env"}
    
    @property
    def POPULAR_COINS(self) -> List[str]:
        """Return POPULAR_COINS as a list."""
        return [coin.strip() for coin in self.POPULAR_COINS_STR.split(',') if coin.strip()]

# Single instance to be imported by other modules
settings = Settings()