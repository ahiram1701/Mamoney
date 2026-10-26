import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Globe, Loader2, PowerOff } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import { useAuthStatus, useSettings, useTailscale } from "../api/hooks";
import type { TailscaleStatus } from "../api/types";

function QrCode({ text }: { text: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    QRCode.toString(text, { type: "svg", margin: 1, errorCorrectionLevel: "M" }).then((s) => {
      if (alive) setSvg(s);
    });
    return () => {
      alive = false;
    };
  }, [text]);
  if (!svg) return null;
  return (
    <div
      role="img"
      aria-label={`Código QR de ${text}`}
      className="size-32 shrink-0 rounded-lg bg-white p-1.5"
      // SVG generado localmente por la librería a partir de la URL, no de datos externos.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* el portapapeles no está disponible */
    }
  };
  return (
    <button className="btn btn-sm" onClick={copy} aria-label="Copiar dirección">
      {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copiada" : "Copiar"}
    </button>
  );
}

export function TailscalePanel() {
  const qc = useQueryClient();
  const { data: ts, isLoading } = useTailscale();
  const { data: auth } = useAuthStatus();
  const { data: settings } = useSettings();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const run = async (action: "publish" | "unpublish") => {
    setBusy(true);
    setError(null);
    try {
      const status = await api<TailscaleStatus>(`/api/tailscale/${action}`, { method: "POST" });
      qc.setQueryData(["tailscale"], status);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  const restrictToMe = async () => {
    if (!ts?.login) return;
    await api("/api/settings", { method: "PATCH", json: { allowed_logins: [ts.login] } });
    qc.invalidateQueries({ queryKey: ["settings"] });
  };

  if (isLoading) return <p className="text-sm text-ink-3">Revisando Tailscale…</p>;
  if (!ts) return null;

  if (!ts.installed) {
    return (
      <div className="rounded-lg border border-dashed border-line p-4 text-sm">
        <p className="font-medium">Tailscale no está instalado en este equipo</p>
        <p className="mt-1 text-ink-2">
          Instálalo aquí y en tu teléfono con la misma cuenta para abrir Mamoney desde cualquier
          lugar, sin exponerlo a internet.
        </p>
        <a
          className="btn btn-sm mt-3"
          href="https://tailscale.com/download"
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink size={14} /> Descargar Tailscale
        </a>
      </div>
    );
  }

  const canChange = auth?.is_local;
  const unrestricted = (settings?.allowed_logins.length ?? 0) === 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
            ts.published ? "bg-accent-soft text-ink" : "bg-surface-2 text-ink-2"
          }`}
        >
          <Globe size={14} aria-hidden />
          {ts.published ? "Publicado en tu tailnet" : "No publicado"}
        </span>
        {ts.hostname && (
          <span className="text-xs text-ink-3">
            Equipo: {ts.hostname}
            {ts.login && ` · Cuenta: ${ts.login}`}
          </span>
        )}
      </div>

      {ts.error && <p className="text-sm text-critical">{ts.error}</p>}

      {ts.published && ts.url && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-line p-3">
          <QrCode text={ts.url} />
          <div className="min-w-0 flex-1 space-y-2 text-sm">
            <p className="text-ink-2">
              Ábrelo desde cualquier dispositivo con Tailscale conectado, o escanea el código con la
              cámara del teléfono:
            </p>
            <p className="break-all font-medium">{ts.url}</p>
            <div className="flex flex-wrap gap-2">
              <CopyButton text={ts.url} />
              <a className="btn btn-sm" href={ts.url} target="_blank" rel="noreferrer">
                <ExternalLink size={14} /> Abrir
              </a>
            </div>
          </div>
        </div>
      )}

      {ts.published && unrestricted && ts.login && canChange && (
        <div className="rounded-lg bg-surface-2 p-3 text-sm">
          <p>
            Cualquier usuario de tu tailnet puede entrar. ¿Limitar el acceso solo a{" "}
            <strong>{ts.login}</strong>?
          </p>
          <button className="btn btn-sm mt-2" onClick={restrictToMe}>
            Permitir solo mi cuenta
          </button>
        </div>
      )}

      {canChange ? (
        <div className="flex flex-wrap gap-2">
          {ts.published ? (
            <button className="btn" onClick={() => run("unpublish")} disabled={busy}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : <PowerOff size={14} />}
              Dejar de publicar
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={() => run("publish")}
              disabled={busy || !ts.running}
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
              Publicar en Tailscale
            </button>
          )}
        </div>
      ) : (
        <p className="text-xs text-ink-3">
          La publicación se cambia desde el equipo donde corre Mamoney.
        </p>
      )}

      {error && (
        <div role="alert" className="text-sm text-critical">
          <p>{error.message}</p>
          {error instanceof ApiError && error.actionUrl && (
            <a className="btn btn-sm mt-2" href={error.actionUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> Abrir enlace de Tailscale
            </a>
          )}
        </div>
      )}

      <p className="text-xs text-ink-3">
        Usa <code>tailscale serve</code>: solo tus dispositivos lo ven, con HTTPS. Nunca se publica
        en internet.
      </p>
    </div>
  );
}
