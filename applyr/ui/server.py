"""FastAPI app factory + dev server runner for `applyr ui`.

Every import of FastAPI/uvicorn/pydantic lives inside function bodies here,
never at module level — `applyr/cli.py` imports this module only from inside
the `ui` command branch, and even that import must be safe to attempt (and
fail cleanly) when the `[ui]` extra isn't installed. See the `ui` branch in
cli.py for the try/except that turns a missing-dependency ImportError into a
clean `die()` instead of a traceback.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

_STATUS_CODES_TO_ERROR_CODE = {404: "not_found", 422: "invalid_value"}

_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def create_app():
    """Build the FastAPI app: routes + CORS (localhost only) + JSON errors."""
    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from applyr.ui.api import router

    app = FastAPI(title="applyr ui")

    # Local single-user tool (docs/visual-ui/AGENTS.md) — the only other
    # origin is the Vite dev server for the frontend scaffold in this slice.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES_TO_ERROR_CODE.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": True, "code": code, "message": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": True, "code": "invalid_value", "message": str(exc.errors())},
        )

    return app


def _start_frontend() -> subprocess.Popen | None:
    """Start the Vite dev server for the React frontend.

    Returns the subprocess if started successfully, None otherwise.
    Gracefully degrades if node or node_modules are missing.
    """
    if not _FRONTEND_DIR.exists():
        return None

    if not shutil.which("node"):
        print("  ⚠ node not found — frontend not started (install Node.js)")
        return None

    node_modules = _FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("  ⚠ node_modules not found — run 'npm install' in applyr/ui/frontend/")
        return None

    try:
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(_FRONTEND_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except FileNotFoundError:
        return None


def run(host: str = "127.0.0.1", port: int = 8000, *,
        start_frontend: bool = True) -> None:
    """Start the dev server. Blocks until interrupted (Ctrl+C).

    When *start_frontend* is True (the default), also starts the Vite
    dev server for the React UI on port 5173.

    Raises ImportError if uvicorn/fastapi aren't installed — the caller
    (`applyr ui` in cli.py) is responsible for catching that and printing the
    `pip install applyr[ui]` hint instead of letting a traceback through.
    """
    import uvicorn

    frontend_proc = None
    if start_frontend:
        frontend_proc = _start_frontend()
        if frontend_proc:
            print("  Frontend (Vite) running at http://127.0.0.1:5173")

    app = create_app()
    print(f"  Backend (API)  running at http://{host}:{port}")
    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        if frontend_proc:
            frontend_proc.terminate()
            frontend_proc.wait()
