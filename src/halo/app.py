"""Minimal API surface. Run locally: ``make serve`` -> http://127.0.0.1:8000/health"""

from fastapi import FastAPI

from halo.llm import model_name

app = FastAPI(title="HALO")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": model_name()}
