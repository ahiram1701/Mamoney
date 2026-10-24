# Política de seguridad

## Versiones con soporte

Solo la versión más reciente publicada en [Releases](https://github.com/ahiram1701/Mamoney/releases)
recibe correcciones de seguridad.

## Reportar una vulnerabilidad

**No abras un issue público.** Usa el reporte privado de GitHub:
pestaña **Security → Report a vulnerability** del repositorio.

Incluye la versión afectada, los pasos para reproducir y el impacto. Recibirás respuesta en un
plazo de 7 días y se te mantendrá informado hasta la corrección.

## Modelo de amenazas

Mamoney está diseñado para un solo usuario y para ejecutarse en su propio equipo:

- El servidor escucha únicamente en `127.0.0.1`.
- El acceso remoto se hace solo a través de `tailscale serve` dentro de la tailnet del usuario.
  Las peticiones sin la cabecera `Tailscale-User-Login` que no provengan de la ventana local se
  rechazan (esto incluye Tailscale Funnel).
- Se puede restringir el acceso a usuarios de Tailscale concretos y exigir un PIN
  (`scrypt` + sesión firmada con HMAC).
- Los datos se guardan sin cifrar en `%APPDATA%\Mamoney`; protégelos con el cifrado de disco
  del sistema operativo (BitLocker) y con respaldos.

Fuera de alcance: exponer Mamoney directamente a internet, proxies inversos de terceros o
ejecutarlo en equipos compartidos con usuarios no confiables.
