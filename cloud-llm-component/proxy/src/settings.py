from typing import Literal, Optional
from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings

class LLMProxySettings(BaseSettings):
    
    api_key: Optional[SecretStr] = Field(
        default=SecretStr(""),
        repr=False,
        description="The local API key used for authenticating requests from applications to the proxy",
        alias="LOCAL_API_KEY"
    )


    cloud_api_key: SecretStr = Field(
        default=SecretStr(""),
        repr=False,
        description="The cloud API key used for authenticating requests from the proxy to the cloud ai endpoint",
        alias="CLOUD_API_KEY"
    )

    cloud_url: HttpUrl = Field(
        description="The cloud endpoint URL",
    )

    cloud_model_id: Optional[str] = Field(
        default=None,
        description="The cloud model identifier to rewrite incoming model names to when forwarding requests.",
        alias="CLOUD_MODEL_ID"
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]  = Field(
        default="INFO",
        description="The proxies log level."
    )