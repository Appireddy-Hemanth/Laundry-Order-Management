from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.routes import router
from app.storage import init_storage

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "frontend.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_storage()
    yield

app = FastAPI(
    title="Mini Laundry Order Management System",
    description="Simple FastAPI app for managing laundry orders",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow local frontend clients (including VS Code Live Server) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def health_check() -> dict:
    return {"message": "Mini Laundry Order Management API is running"}


@app.get("/ui", include_in_schema=False)
def frontend_ui() -> FileResponse:
    return FileResponse(FRONTEND_FILE)
