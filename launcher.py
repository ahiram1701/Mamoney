"""Mamoney de escritorio: servidor local + ventana nativa + icono en la bandeja.

Cerrar la ventana solo la oculta: el servidor sigue activo para el acceso remoto por
Tailscale. Para terminar por completo se usa "Salir" en el icono de la bandeja.
"""

import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# En el ejecutable de PyInstaller el paquete ya está incluido; desde el código, se
# añade backend/ al path.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import httpx
import pystray
import uvicorn
import webview
from PIL import Image, ImageDraw

from mamoney.config import get_config
from mamoney.main import app
from mamoney.routers.system import backup_database

log = logging.getLogger("mamoney.launcher")
APP_NAME = "Mamoney"


class Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # se ejecuta en un hilo secundario
        pass


def start_server() -> Server:
    cfg = get_config()
    server = Server(uvicorn.Config(app, host=cfg.host, port=cfg.port, log_level="info"))
    threading.Thread(target=server.run, daemon=True, name="uvicorn").start()
    url = f"http://127.0.0.1:{cfg.port}/api/health"
    for _ in range(100):
        try:
            if httpx.get(url, timeout=0.5).status_code == 200:
                return server
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"El servidor no arrancó en el puerto {cfg.port}")


def tray_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, 63, 63), radius=14, fill="#0f6b4f")
    draw.line(
        [(14, 46), (14, 20), (23, 34), (32, 20), (41, 34), (50, 20), (50, 46)],
        fill="white",
        width=5,
    )
    return img


def startup_shortcut() -> Path:
    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
    return startup / f"{APP_NAME}.bat"


def autostart_enabled(_item: object = None) -> bool:
    return startup_shortcut().exists()


def toggle_autostart() -> None:
    path = startup_shortcut()
    if path.exists():
        path.unlink()
        return
    if getattr(sys, "frozen", False):
        command = f'start "" "{sys.executable}" --hidden'
    else:
        command = f'start "" "{sys.executable}" "{Path(__file__).resolve()}" --hidden'
    path.write_text(f"@echo off\r\n{command}\r\n", encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = get_config()
    server = start_server()
    url = f"http://127.0.0.1:{cfg.port}/"

    created = webview.create_window(
        APP_NAME, url, width=1360, height=880, min_size=(420, 600), hidden="--hidden" in sys.argv
    )
    if created is None:
        raise RuntimeError("No se pudo crear la ventana de Mamoney")
    window = created

    def on_closing() -> bool:
        window.hide()
        return False  # cancela el cierre: la app sigue en la bandeja

    window.events.closing += on_closing

    def show(_icon: object = None, _item: object = None) -> None:
        window.show()
        window.restore()

    def backup(_icon: pystray.Icon, _item: object) -> None:
        cfg.backup_dir.mkdir(parents=True, exist_ok=True)
        target = cfg.backup_dir / f"mamoney-{time.strftime('%Y%m%d-%H%M%S')}.db"
        backup_database(target)
        _icon.notify(f"Respaldo guardado en {target}", APP_NAME)

    def quit_app(icon: pystray.Icon, _item: object) -> None:
        icon.stop()
        server.should_exit = True
        window.events.closing -= on_closing
        window.destroy()

    icon = pystray.Icon(
        APP_NAME,
        tray_image(),
        APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Abrir Mamoney", show, default=True),
            pystray.MenuItem("Abrir en el navegador", lambda: webbrowser.open(url)),
            pystray.MenuItem("Respaldar ahora", backup),
            pystray.MenuItem(
                "Iniciar con Windows", lambda: toggle_autostart(), checked=autostart_enabled
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", quit_app),
        ),
    )
    icon.run_detached()
    webview.start(private_mode=False)
    server.should_exit = True


if __name__ == "__main__":
    main()
