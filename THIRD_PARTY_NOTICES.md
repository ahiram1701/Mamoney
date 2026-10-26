# Avisos de terceros

Mamoney es software propietario (ver [LICENSE](LICENSE)), pero incluye o usa los
siguientes componentes de código abierto, cada uno bajo su propia licencia. Sus
licencias completas acompañan a cada paquete en su distribución original.

## Incluidos en la app de escritorio (Python)

| Componente | Licencia |
|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | MIT |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause |
| [Pydantic](https://github.com/pydantic/pydantic) y pydantic-core | MIT |
| [SQLModel](https://github.com/fastapi/sqlmodel) | MIT |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | MIT |
| [Alembic](https://github.com/sqlalchemy/alembic) | MIT |
| [Mako](https://github.com/sqlalchemy/mako) | MIT |
| [HTTPX](https://github.com/encode/httpx) y httpcore | BSD-3-Clause |
| [AnyIO](https://github.com/agronholm/anyio) | MIT |
| [h11](https://github.com/python-hyper/h11) | MIT |
| [idna](https://github.com/kjd/idna) | BSD-3-Clause |
| [certifi](https://github.com/certifi/python-certifi) | MPL-2.0 |
| [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 |
| [Click](https://github.com/pallets/click) | BSD-3-Clause |
| [MarkupSafe](https://github.com/pallets/markupsafe) | BSD-3-Clause |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause |
| [pythonnet](https://github.com/pythonnet/pythonnet) y clr-loader | MIT |
| [bottle](https://github.com/bottlepy/bottle) | MIT |
| [proxy_tools](https://github.com/jtushman/proxy_tools) | MIT |
| [pystray](https://github.com/moses-palmer/pystray) | **LGPL-3.0** |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU |
| [six](https://github.com/benjaminp/six) | MIT |
| [colorama](https://github.com/tartley/colorama) | BSD-3-Clause |
| [cffi](https://github.com/python-cffi/cffi) / pycparser | MIT-0 / BSD-3-Clause |
| typing-extensions | PSF-2.0 |
| annotated-types, typing-inspection, annotated-doc | MIT |
| [Python](https://www.python.org/) (intérprete incluido por PyInstaller) | PSF-2.0 |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) (bootloader) | GPL-2.0 con excepción de bootloader |

### Nota sobre pystray (LGPL-3.0)

pystray se distribuye sin modificar y como módulo independiente dentro de la carpeta
`_internal` del ejecutable, por lo que puedes sustituirlo por otra versión compatible.
Su código fuente está disponible en <https://github.com/moses-palmer/pystray>.

## Incluidos en el dashboard web (JavaScript)

| Componente | Licencia |
|---|---|
| [React](https://github.com/facebook/react) y React DOM | MIT |
| [React Router](https://github.com/remix-run/react-router) | MIT |
| [TanStack Query](https://github.com/TanStack/query) | MIT |
| [Recharts](https://github.com/recharts/recharts) | MIT |
| [Lucide](https://github.com/lucide-icons/lucide) | ISC |
| [clsx](https://github.com/lukeed/clsx) | MIT |
| [node-qrcode](https://github.com/soldair/node-qrcode) | MIT |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) (estilos generados) | MIT |

## Servicios externos

- **Frankfurter** (<https://frankfurter.dev>): API pública de tipos de cambio del
  Banco Central Europeo. Mamoney solo envía la lista de monedas a consultar; nunca
  envía tus datos financieros.
