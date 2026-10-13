"""Runtime settings, read from environment variables or a .env file.

The LLM endpoint is any OpenAI-compatible server. The default targets a local
Ollama instance, so no hosted API or GPU is required.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MANUAL_ASSISTANT_", env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:3b-instruct"
    llm_api_key: str = "ollama"
    manuals_dir: Path = Path("data/manuals")

    @property
    def uses_local_llm(self) -> bool:
        return "localhost" in self.llm_base_url or "127.0.0.1" in self.llm_base_url
