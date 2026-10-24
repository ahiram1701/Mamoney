# Cómo colaborar

Gracias por tu interés en Mamoney. Es un proyecto **propietario con código visible**
(ver [LICENSE](LICENSE)), así que la colaboración funciona así:

## Sí, por favor

- **Reportar errores** con la plantilla de *Reporte de error*: versión, pasos para reproducir,
  comportamiento esperado y capturas (sin datos financieros reales).
- **Proponer mejoras** con la plantilla de *Propuesta de mejora*.
- **Reportar vulnerabilidades** de forma privada según [SECURITY.md](SECURITY.md).

## Pull requests

No se aceptan pull requests sin un acuerdo previo por escrito que ceda o licencie al titular
los derechos sobre la contribución. Esto mantiene la titularidad única del código. Si quieres
contribuir código, abre primero un issue para conversarlo.

## Estándares del proyecto

- Python: Ruff (lint y formato), mypy y pytest; la lógica de dominio en `services/` va con pruebas.
- Frontend: ESLint, Prettier, TypeScript estricto y Vitest.
- Commits en español, en imperativo y con un tema por commit (por ejemplo, "Agrega importación CSV").
- Cada cambio visible se documenta en [CHANGELOG.md](CHANGELOG.md).
- Los cambios de modelo de datos incluyen su migración de Alembic (`alembic check` debe pasar).
