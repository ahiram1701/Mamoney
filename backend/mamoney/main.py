"""Aplicación FastAPI: API en /api y el dashboard compilado en /."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from mamoney import __version__
from mamoney.config import get_config
from mamoney.db import get_engine, init_db
from mamoney.routers import (
    analytics,
    assets,
    expenses,
    fx,
    income,
    portfolio,
    system,
    tailscale,
    updates,
)
from mamoney.security import PUBLIC_PATHS, evaluate
from mamoney.services import updater
from mamoney.services.fx import refresh_rates
from mamoney.settings_store import get_setting

if TYPE_CHECKING:
    import uvicorn

log = logging.getLogger("mamoney")

FX_REFRESH_SECONDS = 6 * 60 * 60
UPDATE_CHECK_SECONDS = 6 * 60 * 60
QUOTES_REFRESH_SECONDS = 30 * 60


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


async def _quotes_loop() -> None:
    from mamoney.services.portfolio import refresh_prices

    await asyncio.sleep(5)
    while True:
        try:
            with Session(get_engine()) as session:
                result = await asyncio.to_thread(refresh_prices, session)
                if result["updated"] or result["failed"]:
                    log.info("Cotizaciones actualizadas: %s", result)
        except Exception:
            log.exception("Fallo al actualizar cotizaciones")
        await asyncio.sleep(QUOTES_REFRESH_SECONDS)


async def _update_loop() -> None:
    await asyncio.sleep(10)  # no competir con el arranque
    while True:
        try:
            with Session(get_engine()) as session:
                enabled = bool(get_setting(session, "auto_update_check"))
            if enabled:
                status = await asyncio.to_thread(updater.check_for_updates)
                if status.available and status.latest:
                    log.info("Nueva versión disponible: v%s", status.latest.version)
        except Exception:
            log.exception("Fallo al buscar actualizaciones")
        await asyncio.sleep(UPDATE_CHECK_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    cfg = get_config()
    tasks = []
    if cfg.fx_auto_update:
        tasks.append(asyncio.create_task(_fx_loop()))
    if cfg.update_check:
        tasks.append(asyncio.create_task(_update_loop()))
    if cfg.quotes_auto_update:
        tasks.append(asyncio.create_task(_quotes_loop()))
    yield
    for task in tasks:
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

    for module in (
        assets,
        income,
        expenses,
        fx,
        analytics,
        portfolio,
        system,
        updates,
        tailscale,
    ):
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


def server_config(**overrides: Any) -> "uvicorn.Config":
    """Configuración de Uvicorn compartida por el servidor y la app de escritorio.

    `proxy_headers=False` es imprescindible: `tailscale serve` se conecta desde 127.0.0.1 y
    añade `X-Forwarded-For` con la IP del teléfono. Si Uvicorn confiara en esa cabecera,
    reescribiría el cliente con esa IP y el control de acceso rechazaría a la propia tailnet.
    La identidad del usuario se toma de `Tailscale-User-Login`, no de la IP.
    """
    import uvicorn

    cfg = get_config()
    options: dict[str, Any] = {"host": cfg.host, "port": cfg.port, "proxy_headers": False}
    options.update(overrides)
    return uvicorn.Config(app, **options)


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.Server(server_config(log_level="info")).run()


if __name__ == "__main__":
    run()
