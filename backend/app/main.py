import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import access, admin, audit, auth, calibrations, dashboard, ingest, instruments, reports, usage

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="CAD - Lab Calibration & Access Tracker", version="1.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
    allow_methods=["*"], allow_headers=["Authorization", "Content-Type", "X-Device-Key"],
)

api = APIRouter(prefix="/api")
for r in (auth, admin, instruments, calibrations, usage, access, ingest, audit, dashboard, reports):
    api.include_router(r.router)


@api.get("/health", tags=["system"])
def health():
    return {"status": "ok", "env": settings.env}


app.include_router(api)

# Single-process local mode: serve the built React app. On AWS the frontend lives in S3 + CloudFront instead.
_dist = settings.frontend_dist
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (_dist / path).resolve()
        if path and _dist.resolve() in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
