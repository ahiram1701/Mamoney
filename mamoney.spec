# -*- mode: python ; coding: utf-8 -*-
# Construye la app de escritorio:  uv run pyinstaller mamoney.spec --noconfirm
# Requiere el frontend compilado en frontend/dist (npm run build).

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

if not (ROOT / "frontend" / "dist" / "index.html").exists():
    raise SystemExit("Falta frontend/dist: ejecuta `npm run build` en frontend/ primero.")

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "backend" / "mamoney" / "migrations"), "mamoney/migrations"),
    (str(ROOT / "assets" / "mamoney.png"), "assets"),
]

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("mamoney")
    + ["sqlmodel.sql.sqltypes", "logging.config"]
)

a = Analysis(
    ["launcher.py"],
    pathex=[str(ROOT / "backend")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Mamoney",
    icon=str(ROOT / "assets" / "mamoney.ico"),
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Mamoney", upx=False)
