import { useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, Loader2, Sparkles, X } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import { useAuthStatus, useUpdateStatus } from "../api/hooks";
import { ErrorText } from "./ui";

const DISMISS_KEY = "mamoney-update-dismissed";

function readDismissed(): string | null {
  try {
    return localStorage.getItem(DISMISS_KEY);
  } catch {
    return null;
  }
}

/** Espera a que el servidor vuelva con la versión nueva y recarga la página. */
async function waitForRestart(version: string) {
  for (let i = 0; i < 90; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const health = await api<{ version: string }>("/api/health");
      if (health.version === version) {
        window.location.reload();
        return;
      }
    } catch {
      /* el servidor sigue reiniciando */
    }
  }
}

function useInstallUpdate() {
  const qc = useQueryClient();
  const [state, setState] = useState<"idle" | "installing" | "restarting">("idle");
  const [error, setError] = useState<unknown>(null);
  const install = async () => {
    setError(null);
    setState("installing");
    try {
      const { installing } = await api<{ installing: string }>("/api/updates/install", {
        method: "POST",
      });
      setState("restarting");
      await waitForRestart(installing);
    } catch (err) {
      setError(err);
      setState("idle");
      qc.invalidateQueries({ queryKey: ["updates"] });
    }
  };
  return { install, state, error };
}

export function InstallButton({ className = "btn btn-primary btn-sm" }: { className?: string }) {
  const { install, state, error } = useInstallUpdate();
  return (
    <>
      <button className={className} onClick={install} disabled={state !== "idle"}>
        {state === "idle" ? <Download size={14} /> : <Loader2 size={14} className="animate-spin" />}
        {state === "idle" && "Instalar y reiniciar"}
        {state === "installing" && "Descargando y verificando…"}
        {state === "restarting" && "Reiniciando Mamoney…"}
      </button>
      <ErrorText error={error} />
    </>
  );
}

export function UpdateBanner() {
  const { data: status } = useUpdateStatus();
  const { data: auth } = useAuthStatus();
  const [dismissed, setDismissed] = useState(readDismissed);
  const [showNotes, setShowNotes] = useState(false);

  const latest = status?.latest;
  if (!status?.available || !latest || dismissed === latest.version) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, latest.version);
    } catch {
      /* almacenamiento no disponible */
    }
    setDismissed(latest.version);
  };

  return (
    <div role="status" className="mb-5 rounded-xl border border-line bg-accent-soft p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Sparkles size={18} className="shrink-0 text-accent" aria-hidden />
        <p className="min-w-0 flex-1">
          <strong>Mamoney v{latest.version}</strong> está disponible (tienes v{status.current}).{" "}
          {latest.notes && (
            <button className="underline" onClick={() => setShowNotes((v) => !v)}>
              {showNotes ? "Ocultar novedades" : "Ver novedades"}
            </button>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {status.can_install && auth?.is_local ? (
            <InstallButton />
          ) : (
            <a className="btn btn-sm" href={latest.html_url} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> {auth?.is_local ? "Descargar" : "Ver versión"}
            </a>
          )}
          <button className="btn btn-sm" onClick={dismiss} aria-label="Ocultar aviso">
            <X size={14} />
          </button>
        </div>
      </div>
      {!auth?.is_local && status.can_install && (
        <p className="mt-2 text-xs text-ink-2">
          Por seguridad, la instalación se hace desde el equipo donde corre Mamoney.
        </p>
      )}
      {showNotes && (
        <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 font-sans text-xs text-ink-2">
          {latest.notes.replace(/^#+\s*/gm, "")}
        </pre>
      )}
    </div>
  );
}
