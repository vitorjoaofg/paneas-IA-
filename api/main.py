from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from config import get_settings
from middleware.auth import AuthMiddleware
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_id import RequestIDMiddleware
from routers import align, analytics, asr, asr_stream, health, llm, ocr, tts
from services.http_client import close_http_client
from services.redis_client import close_redis
from services.insight_manager import insight_manager
from telemetry.logging import configure_logging
from telemetry.tracing import configure_tracing

settings = get_settings()

configure_logging(settings.log_level)
configure_tracing()

app = FastAPI(
    title="AI Stack Platform API",
    version=settings.stack_version,
    default_response_class=ORJSONResponse,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)

instrumentator = Instrumentator(should_group_status_codes=True)
instrumentator.instrument(app).expose(app, include_in_schema=False)

app.include_router(health.router)
app.include_router(asr.router)
app.include_router(asr_stream.router)
app.include_router(align.router)
app.include_router(ocr.router)
app.include_router(tts.router)
app.include_router(llm.router)
app.include_router(analytics.router)


@app.on_event("startup")
async def startup_event() -> None:
    await insight_manager.startup()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await insight_manager.shutdown()
    await close_http_client()
    await close_redis()
