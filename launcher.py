"""Mamoney de escritorio: servidor local + ventana nativa + icono en la bandeja.

Cerrar la ventana solo la oculta: el servidor sigue activo para el acceso remoto por
Tailscale. Para terminar por completo se usa "Salir" en el icono de la bandeja.
"""

import logging
import logging.handlers
import os
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

APP_NAME = "Mamoney"
FROZEN = bool(getattr(sys, "frozen", False))


def unblock_bundle() -> int:
    """Quita la marca "descargado de internet" (Mark of the Web) de los archivos de la app.

    Al descomprimir el .zip descargado con el navegador, Windows marca cada archivo con un
    flujo `Zone.Identifier`. .NET Framework se niega a cargar ensamblados marcados, así que
    pywebview no puede abrir la ventana. Equivale a "Desbloquear" en las propiedades del
    archivo y solo toca la carpeta de la propia app.
    """
    if not FROZEN or sys.platform != "win32":
        return 0
    root = Path(sys.executable).resolve().parent
    probe = root / "_internal" / "pythonnet" / "runtime" / "Python.Runtime.dll"
    if not os.path.exists(f"{probe}:Zone.Identifier"):
        return 0  # sin marca (instalada por el actualizador o ya desbloqueada)
    removed = 0
    for folder, _dirs, files in os.walk(root):
        for name in files:
            try:
                os.remove(os.path.join(folder, f"{name}:Zone.Identifier"))
                removed += 1
            except OSError:
                pass
    return removed


# Debe ocurrir antes de importar pywebview/pythonnet.
UNBLOCKED = unblock_bundle()

# En el ejecutable de PyInstaller el paquete ya está incluido; desde el código, se
# añade backend/ al path.
if not FROZEN:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import httpx
import pystray
import uvicorn
from PIL import Image, ImageDraw

from mamoney.config import get_config
from mamoney.main import server_config
from mamoney.routers.system import backup_database
from mamoney.services import updater

log = logging.getLogger("mamoney.launcher")


def setup_logging() -> Path:
    log_file = get_config().data_dir / "mamoney.log"
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:  # el .exe sin consola no tiene stderr
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_file


def show_error(message: str) -> None:
    """Muestra un aviso nativo (no depende de pywebview ni de la bandeja)."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    else:
        print(message, file=sys.stderr)


class Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # se ejecuta en un hilo secundario
        pass


def health_url() -> str:
    return f"http://127.0.0.1:{get_config().port}/api/health"


def already_running() -> bool:
    try:
        return httpx.get(health_url(), timeout=0.5).status_code == 200
    except httpx.HTTPError:
        return False


def start_server() -> Server:
    cfg = get_config()
    server = Server(server_config(log_config=None))
    threading.Thread(target=server.run, daemon=True, name="uvicorn").start()
    for _ in range(150):
        if already_running():
            return server
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
    if FROZEN:
        command = f'start "" "{sys.executable}" --hidden'
    else:
        command = f'start "" "{sys.executable}" "{Path(__file__).resolve()}" --hidden'
    path.write_text(f"@echo off\r\n{command}\r\n", encoding="utf-8")


def run() -> None:
    cfg = get_config()
    url = f"http://127.0.0.1:{cfg.port}/"
    hidden = "--hidden" in sys.argv

    if already_running():
        # Ya hay un Mamoney abierto: se muestra su dashboard en lugar de pelear por el puerto.
        log.info("Mamoney ya está en ejecución; se abre el dashboard existente")
        if not hidden:
            webbrowser.open(url)
        return

    if UNBLOCKED:
        log.info("Se quitó la marca de descarga de %s archivos", UNBLOCKED)
    server = start_server()
    stop = threading.Event()
    window = None  # se asigna si pywebview logra crear la ventana

    def show(_icon: object = None, _item: object = None) -> None:
        if window is not None:
            window.show()
            window.restore()
        else:
            webbrowser.open(url)

    def backup(_icon: pystray.Icon, _item: object) -> None:
        cfg.backup_dir.mkdir(parents=True, exist_ok=True)
        target = cfg.backup_dir / f"mamoney-{time.strftime('%Y%m%d-%H%M%S')}.db"
        backup_database(target)
        _icon.notify(f"Respaldo guardado en {target}", APP_NAME)

    def shutdown() -> None:
        icon.stop()
        server.should_exit = True
        stop.set()
        if window is not None:
            window.events.closing -= on_closing
            window.destroy()

    def quit_app(_icon: pystray.Icon, _item: object) -> None:
        shutdown()

    updater.set_shutdown_handler(shutdown)

    def update_label(_item: object) -> str:
        status = updater.last_status()
        version = status.latest.version if status and status.latest else ""
        return f"Instalar actualización v{version}"

    def update_visible(_item: object) -> bool:
        status = updater.last_status()
        return bool(status and status.can_install and not status.installing)

    def install_update(_icon: pystray.Icon, _item: object) -> None:
        def task() -> None:
            try:
                icon.notify("Descargando y verificando la actualización…", APP_NAME)
                updater.install_update()
            except updater.UpdateError as exc:
                icon.notify(str(exc), APP_NAME)

        threading.Thread(target=task, daemon=True, name="update").start()

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
            pystray.MenuItem(update_label, install_update, visible=update_visible),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", quit_app),
        ),
    )
    icon.run_detached()

    def watch_updates() -> None:
        """Avisa una sola vez por versión nueva y muestra la opción en el menú."""
        notified: str | None = None
        while not stop.is_set():
            status = updater.last_status()
            if status and status.available and status.latest:
                if status.latest.version != notified:
                    notified = status.latest.version
                    icon.notify(
                        f"Mamoney v{notified} está disponible. Instálala desde este menú "
                        "o desde el dashboard.",
                        APP_NAME,
                    )
                icon.update_menu()
            stop.wait(60)

    threading.Thread(target=watch_updates, daemon=True, name="update-watch").start()

    def watch_alerts() -> None:
        """Pagos por vencer, presupuesto excedido y metas atrasadas: un aviso por alerta."""
        from sqlmodel import Session

        from mamoney.db import get_engine
        from mamoney.services.alerts import take_new_alerts

        stop.wait(20)  # deja arrancar la app antes del primer aviso
        while not stop.is_set():
            try:
                with Session(get_engine()) as session:
                    fresh = take_new_alerts(session)
                if len(fresh) == 1:
                    icon.notify(f"{fresh[0]['title']}. {fresh[0]['detail']}", APP_NAME)
                elif fresh:
                    titles = "; ".join(a["title"] for a in fresh[:3])
                    more = f" y {len(fresh) - 3} más" if len(fresh) > 3 else ""
                    icon.notify(f"{len(fresh)} alertas: {titles}{more}", APP_NAME)
            except Exception:
                log.exception("No se pudieron revisar las alertas")
            stop.wait(30 * 60)

    threading.Thread(target=watch_alerts, daemon=True, name="alerts-watch").start()

    def on_closing() -> bool:
        if window is not None:
            window.hide()
        return False  # cancela el cierre: la app sigue en la bandeja

    try:
        import webview

        window = webview.create_window(
            APP_NAME, url, width=1360, height=880, min_size=(420, 600), hidden=hidden
        )
        if window is None:
            raise RuntimeError("pywebview no devolvió una ventana")
        window.events.closing += on_closing
        webview.start(private_mode=False)
    except Exception:
        # Sin ventana nativa (p. ej. falta WebView2): Mamoney sigue en la bandeja y se usa
        # el navegador predeterminado.
        log.exception("No se pudo abrir la ventana nativa; se usará el navegador")
        window = None
        if not stop.is_set():
            icon.notify(
                "No se pudo abrir la ventana; Mamoney sigue disponible en tu navegador y en "
                "este icono.",
                APP_NAME,
            )
            if not hidden:
                webbrowser.open(url)
            stop.wait()
    server.should_exit = True
    icon.stop()


def enable_stack_traces() -> None:
    """Diagnóstico: con MAMONEY_TRACE_SECONDS vuelca las pilas de todos los hilos cada N s."""
    seconds = os.environ.get("MAMONEY_TRACE_SECONDS")
    if not seconds:
        return
    import faulthandler

    stacks = (get_config().data_dir / "stacks.log").open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(int(seconds), repeat=True, file=stacks)


def main() -> None:
    log_file = setup_logging()
    enable_stack_traces()
    try:
        run()
    except Exception:
        log.exception("Error fatal")
        show_error(
            f"Mamoney no pudo iniciar.\n\n{traceback.format_exc(limit=3)}\nDetalles en: {log_file}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
