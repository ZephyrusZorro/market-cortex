"""Read-only operational diagnostics; refreshing data remains explicit CLI work."""
from datetime import datetime, timezone
from fastapi import APIRouter
from .operations import preflight, status


def router_for(settings):
    router = APIRouter(prefix='/api/v1/operations', tags=['operations'])

    @router.get('/status')
    def read_status():
        return status(settings, datetime.now(timezone.utc))

    @router.get('/preflight')
    def read_preflight():
        return preflight(settings)

    return router
