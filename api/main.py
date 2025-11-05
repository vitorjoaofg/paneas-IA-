from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from config import get_settings
# from middleware.auth import AuthMiddleware
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_id import RequestIDMiddleware
from routers import align, analytics, asr, asr_stream, diar, health, llm, ocr, scrapper, tts, api_keys, auth, processos
from services.http_client import close_http_client
from services.redis_client import close_redis
from services.db_client import get_db_pool, close_db_pool
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

# CORS middleware - deve ser adicionado antes de outros middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware for OAuth (must be before auth middleware)
# TEMPORARILY DISABLED: SessionMiddleware causes 403 errors on WebSocket connections
# Re-enable when OAuth is fully implemented
# app.add_middleware(
#     SessionMiddleware,
#     secret_key=settings.jwt_secret_key,  # Use same key as JWT
#     max_age=3600,  # 1 hour session
# )

app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
# app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)

instrumentator = Instrumentator(should_group_status_codes=True)
instrumentator.instrument(app).expose(app, include_in_schema=False)

app.include_router(health.router)
print(f"[DEBUG] About to include auth router: {auth.router}")
print(f"[DEBUG] Auth router prefix: {auth.router.prefix}")
print(f"[DEBUG] Auth router routes: {[r.path for r in auth.router.routes if hasattr(r, 'path')]}")
app.include_router(auth.router)
print(f"[DEBUG] Auth router included!")
app.include_router(asr.router)
app.include_router(asr_stream.router)
app.include_router(align.router)
app.include_router(ocr.router)
app.include_router(diar.router)
app.include_router(tts.router)
app.include_router(llm.router)
app.include_router(analytics.router)
app.include_router(scrapper.router)
app.include_router(processos.router)
app.include_router(api_keys.router)

# Serve frontend static files
frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


@app.on_event("startup")
async def startup_event() -> None:
    await get_db_pool()  # Initialize database connection pool
    await insight_manager.startup()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await insight_manager.shutdown()
    await close_http_client()
    await close_redis()
    await close_db_pool()
