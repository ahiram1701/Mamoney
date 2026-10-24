from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from mamoney.security import is_local_request
from mamoney.services import updater

router = APIRouter(prefix="/api/updates", tags=["actualizaciones"])


@router.get("")
async def update_status(refresh: bool = False) -> dict[str, Any]:
    status = updater.last_status()
    if refresh or status is None:
        status = await run_in_threadpool(updater.check_for_updates)
    return status.to_dict()


@router.post("/install")
async def install(request: Request) -> dict[str, str]:
    # Reinicia la app: solo se permite desde el propio equipo, no por Tailscale.
    if not is_local_request(request):
        raise HTTPException(403, "Instala las actualizaciones desde el equipo donde corre Mamoney")
    try:
        version = await run_in_threadpool(updater.install_update)
    except updater.UpdateError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"installing": version}
