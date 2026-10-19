from pydantic import BaseModel

from emotion_types import VALID_EMOTIONS, Emotion, EmotionResponse
from llmcall import LLMSession
from settings import settings


_SYSTEM_PROMPT = (
    "You are an expert sentiment classifier. "
    "Given a message, respond with the single emotion that best describes it and how confident you are about the emotion."
    f"Choose the from {VALID_EMOTIONS} and respond in the following JSON format:"
    "```json"
    f"{EmotionResponse.model_json_schema()}"
    "```"
)

_EXAMPLES: list[dict[str, str]] = [
    {"role": "user", "content": "I just got promoted!"},
    {"role": "assistant", "content": f'{EmotionResponse(emotion="excited", confidence=0.75).model_dump_json()}'},
    {"role": "user", "content": "My dog passed away today."},
    {"role": "assistant", "content": f'{EmotionResponse(emotion="sad", confidence=1.0).model_dump_json()}'},
    {"role": "user", "content": "The package arrived damaged again!"},
    {"role": "assistant", "content": f'{EmotionResponse(emotion="angry", confidence=0.9).model_dump_json()}'},
]


# Single session reused for the lifetime of the process.
_session = LLMSession(settings)


def classify(message: str) -> EmotionResponse:
    result = _session.call(
        EmotionResponse,
        message,
        system_prompt=_SYSTEM_PROMPT,
        examples=_EXAMPLES,
    )
    return result
