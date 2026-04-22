"""
Argus-Invest Backend Configuration
"""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    # Project root (parent of backend/)
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

    # Data directory
    DATA_DIR: Path = PROJECT_ROOT / "data"

    # Data subdirectories
    USER_DIR: Path = DATA_DIR / "user"
    KV_DIR: Path = DATA_DIR / "kv"
    MARKET_DIR: Path = DATA_DIR / "market"
    RULES_DIR: Path = DATA_DIR / "rules"
    REPORTS_DIR: Path = DATA_DIR / "reports"

    # Parquet file names
    PORTFOLIO_FILE: str = "portfolio.parquet"
    TRADES_FILE: str = "trades.parquet"
    WEAKNESS_FILE: str = "weakness.parquet"
    THINKING_FILE: str = "thinking.parquet"
    PLAN_FILE: str = "portfolio_plan.parquet"
    MONITOR_FILE: str = "monitor_check.parquet"

    # AI settings
    AI_MODEL: str = "minimax/MiniMax-M2.7"  # default model
    AI_API_BASE: str = "https://api.minimax.chat/v1"

    # MiniMax API key
    MINIMAX_API_KEY: str = ""

    # Mail settings (placeholder)
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Tushare token
    TUSHARE_TOKEN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self) -> None:
        """Ensure all data directories exist."""
        for d in [self.DATA_DIR, self.USER_DIR, self.KV_DIR,
                  self.MARKET_DIR, self.RULES_DIR, self.REPORTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
