"""Control de acceso.

El servidor escucha solo en localhost. Hay dos tipos de cliente:

* **Local**: la ventana de escritorio o un navegador en el mismo PC. Se reconoce porque
  la conexión viene de loopback, el `Host` es localhost y no trae cabeceras de proxy.
* **Remoto vía Tailscale**: `tailscale serve` reenvía la petición desde loopback y añade
  `Tailscale-User-Login` con la identidad verificada del usuario de la tailnet.

Cualquier otra petición (por ejemplo Tailscale Funnel, que no incluye identidad) se
rechaza. Opcionalmente se exige una lista de logins permitidos y un PIN.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import Request
from sqlmodel import Session

from mamoney.settings_store import get_setting, session_secret

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "[::1]"}
IDENTITY_HEADER = "tailscale-user-login"
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded", IDENTITY_HEADER)
SESSION_COOKIE = "mamoney_session"
SESSION_TTL = 60 * 60 * 24 * 30
PUBLIC_PATHS = {"/api/health", "/api/auth/status", "/api/auth/pin"}


@dataclass
class Access:
    allowed: bool
    status: int = 200
    reason: str = ""
    is_local: bool = False
    identity: str | None = None


def _hostname(host_header: str) -> str:
    if host_header.startswith("["):
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0] if ":" in host_header else host_header


def is_local_request(request: Request) -> bool:
    client = request.client.host if request.client else ""
    if client not in LOOPBACK:
        return False
    if any(h in request.headers for h in PROXY_HEADERS):
        return False
    return _hostname(request.headers.get("host", "")) in LOCAL_HOSTNAMES


def hash_pin(pin: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return f"{salt}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_pin(pin, salt), stored)


def make_session_token(secret: str, ttl: int = SESSION_TTL) -> str:
    expires = str(int(time.time()) + ttl)
    sig = hmac.new(secret.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def valid_session_token(secret: str, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expires, sig = token.split(".", 1)
    expected = hmac.new(secret.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected) and expires.isdigit() and int(expires) > time.time()


def evaluate(request: Request, session: Session, check_pin: bool = True) -> Access:
    if is_local_request(request):
        return Access(allowed=True, is_local=True)

    client = request.client.host if request.client else ""
    identity = request.headers.get(IDENTITY_HEADER)
    if client not in LOOPBACK or not identity:
        return Access(False, 403, "Acceso solo desde este equipo o tu tailnet de Tailscale")

    allowed = [x.lower() for x in get_setting(session, "allowed_logins") or []]
    if allowed and identity.lower() not in allowed:
        return Access(False, 403, f"El usuario {identity} no está autorizado", identity=identity)

    if check_pin and get_setting(session, "pin_hash"):
        token = request.cookies.get(SESSION_COOKIE)
        if not valid_session_token(session_secret(session), token):
            return Access(False, 401, "pin_required", identity=identity)

    return Access(allowed=True, identity=identity)
