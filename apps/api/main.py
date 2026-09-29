"""ASGI entrypoint: uvicorn market_cortex.api:app --host 127.0.0.1."""

from market_cortex.api import app

__all__ = ["app"]
