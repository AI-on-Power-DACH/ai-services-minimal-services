from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

from emotion_types import LOG_LEVELS

# This class was copied from the official AI-Services
# (https://github.com/IBM/project-ai-services/blob/main/services/common/settings.py)
# To use the class as written here (with the LLM_ prefix)
# all LLM values automatically provided by the llm service dependency
# must be wired into the correct env variables within the podman spec template 
# see documentation there.
# For a full list of possible values that can be injected 
# take a look at: https://github.com/IBM/project-ai-services/blob/main/docs/dev-guides/byos/02-bundle-structure.md#24-injected-dependency-values-services
class LLMConfig(BaseSettings):
    """LLM model configuration."""
    
    model_config = SettingsConfigDict(env_prefix='LLM_')

    endpoint: str = Field(
        default="",
        description="LLM endpoint URL",
    )

    model: str = Field(
        default="",
        description="LLM model name",
    )

    max_model_len: int = Field(
        default=32768,
        ge=1,
        description="Fallback maximum context length for the configured LLM model",
    )

    token_to_word_ratio_en: float = Field(
        default=0.75,
        gt=0.0,
        le=2.0,
        description="Token to word ratio for English text",
    )

    max_batch_size: int = Field(
        default=32,
        ge=1,
        description="Maximum batch size for LLM service (used for connection pool size)",
    )

    api_key: SecretStr = Field(
        default=SecretStr(""),
        repr=False,
        description="API key for vLLM authentication (optional, read from LLM_API_KEY env var)",
    )

    token_buffer_ratio: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description=(
            "Token buffer ratio to apply when calling LLM APIs. "
            "Reduces max_tokens by this ratio to give the LLM breathing room to respect prompt word limits. "
            "For example, 0.15 means the API limit is set to 85% of the requested tokens, "
            "allowing the LLM to naturally complete before hitting the hard limit. "
            "Range: 0.0 (no buffer) to 0.5 (50% buffer)."
        ),
    )


class Settings(BaseSettings):
    log_level: LOG_LEVELS = Field(
        default="INFO"
    )

    port: int = Field(
        default=9500,
        ge=1024,
        le=65535,
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)

settings = Settings()