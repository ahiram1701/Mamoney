from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from mamoney.config import get_config
from mamoney.routers.common import SessionDep
from mamoney.security import is_local_request
from mamoney.services import updater
from mamoney.settings_store import get_setting

router = APIRouter(prefix="/api/updates", tags=["actualizaciones"])


@router.get("")
async def update_status(session: SessionDep, refresh: bool = False) -> dict[str, Any]:
    status = updater.last_status()
    if refresh:
        status = await run_in_threadpool(updater.check_for_updates)
    elif status is None:
        # Con la revisión automática apagada solo se consulta GitHub al pedirlo ("Buscar ahora").
        enabled = get_config().update_check and bool(get_setting(session, "auto_update_check"))
        if not enabled:
            return updater.UpdateStatus(current=updater.current_version()).to_dict()
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
