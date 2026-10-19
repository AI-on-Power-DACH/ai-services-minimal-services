
from typing import Literal
import typing

from pydantic import BaseModel, Field


type Emotion = Literal['happy', 'sad', 'angry', 'grateful', 'frustrated', 'affectionate', 'shameful', 'proud', 'jealous', 'hopeful',
                       'regretful', 'fearful', 'anxious', 'disappointed', 'excited', 'content', 'compassion']
VALID_EMOTIONS = typing.get_args(Emotion)
type LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class EmotionResponse(BaseModel):
    emotion: Emotion
    confidence: float = Field(
        le=1.0,
        ge=0.0,
        description="How confident the prediction is 1.0 means 100% sure while 0.0 means not accurate.",
    )