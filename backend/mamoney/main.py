"""Aplicación FastAPI: API en /api y el dashboard compilado en /."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from mamoney import __version__
from mamoney.config import get_config
from mamoney.db import get_engine, init_db
from mamoney.routers import analytics, assets, expenses, fx, income, system
from mamoney.security import PUBLIC_PATHS, evaluate
from mamoney.services.fx import refresh_rates

log = logging.getLogger("mamoney")

FX_REFRESH_SECONDS = 6 * 60 * 60


async def _fx_loop() -> None:
    while True:
        try:
            with Session(get_engine()) as session:
                count = await asyncio.to_thread(
                    refresh_rates, session, fx.currencies_in_use(session)
                )
                log.info("Tipos de cambio actualizados: %s", count)
        except Exception:
            log.exception("Fallo al actualizar tipos de cambio")
        await asyncio.sleep(FX_REFRESH_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    task = asyncio.create_task(_fx_loop()) if get_config().fx_auto_update else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mamoney",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.middleware("http")
    async def access_control(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path.startswith("/api") and path not in PUBLIC_PATHS:
            with Session(get_engine()) as session:
                access = evaluate(request, session)
            if not access.allowed:
                return JSONResponse({"detail": access.reason}, status_code=access.status)
        elif not path.startswith("/api"):
            # La interfaz no contiene datos, pero tampoco se sirve a orígenes desconocidos.
            with Session(get_engine()) as session:
                access = evaluate(request, session, check_pin=False)
            if not access.allowed:
                return JSONResponse({"detail": access.reason}, status_code=access.status)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    for module in (assets, income, expenses, fx, analytics, system):
        app.include_router(module.router)

    static_dir = get_config().static_dir
    index = static_dir / "index.html"
    if index.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="static")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (static_dir / path).resolve()
            if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)
    else:

        @app.get("/", include_in_schema=False)
        def no_frontend() -> JSONResponse:
            return JSONResponse(
                {"detail": "Frontend no compilado. Ejecuta `npm run build` en frontend/."},
                status_code=503,
            )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    cfg = get_config()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    run()
