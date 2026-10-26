from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from mamoney.security import is_local_request
from mamoney.services import tailscale

router = APIRouter(prefix="/api/tailscale", tags=["tailscale"])


@router.get("")
async def status() -> dict[str, Any]:
    return (await run_in_threadpool(tailscale.get_status)).to_dict()


def _require_local(request: Request) -> None:
    # Publicar o retirar el acceso remoto solo desde el propio equipo.
    if not is_local_request(request):
        raise HTTPException(403, "Cambia la publicación desde el equipo donde corre Mamoney")


async def _apply(action: Any) -> dict[str, Any]:
    try:
        result: tailscale.TailscaleStatus = await run_in_threadpool(action)
    except tailscale.TailscaleError as exc:
        raise HTTPException(409, {"message": str(exc), "action_url": exc.action_url}) from exc
    return result.to_dict()


@router.post("/publish")
async def publish(request: Request) -> dict[str, Any]:
    _require_local(request)
    return await _apply(tailscale.publish)


@router.post("/unpublish")
async def unpublish(request: Request) -> dict[str, Any]:
    _require_local(request)
    return await _apply(tailscale.unpublish)
