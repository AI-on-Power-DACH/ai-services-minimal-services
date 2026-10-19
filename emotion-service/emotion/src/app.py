from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from classification import classify

app = FastAPI()


class ClassifyRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify")
def classify_route(body: ClassifyRequest):
    try:
        return classify(body.message)
    except Exception as exc:
        # logger.error("Classification failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Classification failed.")