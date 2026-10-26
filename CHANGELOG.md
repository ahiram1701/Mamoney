# Changelog

Todos los cambios relevantes de Mamoney se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semántico](https://semver.org/lang/es/).

## [Unreleased]

### Añadido

- Inversiones: cuentas con posiciones de acciones, ETFs de EE. UU. y cripto. Compras y ventas con
  costo promedio, ganancia realizada y no realizada, precios de Yahoo Finance (respaldo Coinbase
  para cripto) cada 30 min y valuación automática de la cuenta (mensual e histórica).

### Corregido

- Las migraciones desactivan las llaves foráneas: reconstruir una tabla podía borrar en cascada
  las valuaciones. Prueba que migra una base con datos.
- Los estilos de campos y botones permiten utilidades de Tailwind (p. ej. iconos dentro de campos).

## [0.2.4] - 2026-10-25

### Corregido

- El acceso desde otros dispositivos por Tailscale respondía "Acceso solo desde este equipo o tu
  tailnet". Uvicorn confiaba en la cabecera `X-Forwarded-For` de `tailscale serve` y cambiaba la
  IP del cliente; ahora Mamoney usa la conexión real y te identifica con tu cuenta de Tailscale.
- Prueba con un Uvicorn real para que este caso no vuelva a pasar inadvertido.

## [0.2.3] - 2026-10-25

### Añadido

- Ajustes → Acceso remoto: botón para publicar y retirar Mamoney en Tailscale con un clic, con la
  dirección para otros dispositivos, código QR para el teléfono y opción de permitir solo tu
  cuenta. Si Tailscale necesita una autorización (HTTPS o Serve), muestra el enlace para darla.

### Corregido

- En pantallas de teléfono, algunas tarjetas eran más anchas que la pantalla y se cortaban.

## [0.2.2] - 2026-10-25

> La versión 0.2.1 no llegó a publicarse: su verificación del ejecutable se quedó colgada en el
> CI. Todos sus cambios están incluidos aquí.

### Corregido

- Mamoney.exe no abría al descargarlo con el navegador: Windows marca los archivos del `.zip`
  como "descargados de internet" y .NET se negaba a cargar los componentes de la ventana. Ahora la
  app quita esa marca de sus propios archivos al arrancar.

### Añadido

- Si la ventana nativa no puede abrirse (por ejemplo, sin WebView2), Mamoney sigue en la bandeja y
  abre el dashboard en el navegador en lugar de cerrarse.
- Registro en `%APPDATA%\Mamoney\mamoney.log` y aviso claro si la app no puede iniciar.
- Abrir Mamoney cuando ya está en ejecución muestra el dashboard existente en lugar de duplicarlo.
- El CI y el flujo de Release prueban el ejecutable con sus archivos marcados como descargados
  (`scripts/test-exe.ps1`), con tiempos límite y diagnóstico de hilos.
- Con la revisión automática desactivada, Mamoney ya no consulta GitHub al abrir el dashboard;
  solo al pulsar "Buscar ahora".

## [0.2.0] - 2026-10-24

> Esta es la primera versión con actualizador: instálala a mano una vez; las siguientes se
> instalan solas desde Mamoney.

### Añadido

- Actualizaciones desde GitHub Releases: revisión al arrancar y cada 6 h, aviso en el dashboard y en
  la bandeja, e instalación con un clic que verifica el SHA-256, respalda la base de datos y restaura
  la versión anterior si algo falla.
- Ajustes → Actualizaciones: versión instalada, búsqueda manual y opción para desactivar la revisión.

### Corregido

- Las notas de cada release ahora incluyen la sección correspondiente del CHANGELOG.
- El ejecutable incluye los metadatos del paquete para reportar su versión correctamente.

## [0.1.0] - 2026-10-24

### Añadido

- Patrimonio: activos y deudas con historial de valuaciones, liquidez y distribución por tipo, moneda y liquidez.
- Ingresos: fuentes activas y pasivas de cualquier tipo, cobros con impuestos retenidos y gráfica mensual por fuente.
- Gastos fijos con frecuencias semanal, quincenal, mensual, bimestral, trimestral, semestral y anual;
  calendario de vencimientos y control de pagos.
- Análisis: cobertura con ingreso pasivo, colchón de liquidez, deuda/activos, concentración de ingresos,
  rendimiento por activo y proyección de patrimonio.
- Multimoneda con base en MXN y actualización automática de tipos de cambio (Frankfurter/BCE).
- App de escritorio para Windows con ventana nativa, icono en la bandeja e inicio con Windows.
- Acceso remoto vía `tailscale serve` con verificación de identidad, lista de usuarios permitidos y PIN.
- Respaldo de la base de datos y exportación/importación JSON.
- CI/CD con GitHub Actions: pruebas en Ubuntu y Windows, prueba de humo y publicación automática de versiones.

[Unreleased]: https://github.com/ahiram1701/Mamoney/compare/v0.2.4...HEAD
[0.2.4]: https://github.com/ahiram1701/Mamoney/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/ahiram1701/Mamoney/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/ahiram1701/Mamoney/compare/v0.2.0...v0.2.2
[0.2.0]: https://github.com/ahiram1701/Mamoney/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ahiram1701/Mamoney/releases/tag/v0.1.0
