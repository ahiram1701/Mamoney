"""Mamoney: gestor personal de patrimonio, ingresos y gastos fijos."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mamoney")
except PackageNotFoundError:  # ejecutando desde el código sin instalar (p. ej. PyInstaller)
    __version__ = "0.2.5"
