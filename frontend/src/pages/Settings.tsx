import { useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw, Upload } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { api } from "../api/client";
import { useApiMutation, useAuthStatus, useFxLatest, useSettings } from "../api/hooks";
import { Card, ErrorText, Field, PageHeader } from "../components/ui";
import { number, shortDate, todayIso } from "../lib/format";

export function SettingsPage() {
  return (
    <>
      <PageHeader title="Ajustes" />
      <div className="grid gap-4 xl:grid-cols-2">
        <FxCard />
        <AccessCard />
        <PreferencesCard />
        <BackupCard />
      </div>
    </>
  );
}

function FxCard() {
  const { data: rates = [] } = useFxLatest();
  const refresh = useApiMutation<undefined, { updated: number }>("POST", "/api/fx/refresh");
  const add = useApiMutation("POST", "/api/fx/rates");
  const [form, setForm] = useState({ currency: "", rate_to_base: "", date: todayIso() });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await add.mutateAsync({ ...form, rate_to_base: Number(form.rate_to_base) });
    setForm({ currency: "", rate_to_base: "", date: todayIso() });
  };

  return (
    <Card
      title="Tipos de cambio"
      subtitle="MXN por unidad. Se actualizan solos cada 6 h (Banco Central Europeo vía Frankfurter)."
      actions={
        <button
          className="btn btn-sm"
          onClick={() => refresh.mutate(undefined)}
          disabled={refresh.isPending}
        >
          <RefreshCw size={14} className={refresh.isPending ? "animate-spin" : ""} /> Actualizar
        </button>
      }
    >
      {refresh.data && (
        <p className="mb-2 text-xs text-ink-3">{refresh.data.updated} monedas actualizadas.</p>
      )}
      <table className="mb-4 w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-3">
            <th className="py-1.5 font-medium">Moneda</th>
            <th className="py-1.5 text-right font-medium">MXN</th>
            <th className="py-1.5 text-right font-medium">Fecha</th>
            <th className="py-1.5 text-right font-medium">Fuente</th>
          </tr>
        </thead>
        <tbody>
          {rates.map((r) => (
            <tr key={r.currency} className="border-b border-line">
              <td className="py-1.5 font-medium">{r.currency}</td>
              <td className="tabular py-1.5 text-right">
                {r.rate_to_base === null ? (
                  <span className="text-critical">Falta</span>
                ) : (
                  number(r.rate_to_base, 4)
                )}
              </td>
              <td className="tabular py-1.5 text-right text-ink-3">{shortDate(r.date)}</td>
              <td className="py-1.5 text-right text-ink-3">
                {r.source === "manual" ? "Manual" : (r.source ?? "—")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={submit} className="grid grid-cols-[1fr_1fr_1fr_auto] items-end gap-2">
        <Field label="Moneda">
          <input
            className="input uppercase"
            required
            maxLength={8}
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
            placeholder="BTC"
          />
        </Field>
        <Field label="MXN por unidad">
          <input
            className="input"
            type="number"
            step="any"
            min="0"
            required
            value={form.rate_to_base}
            onChange={(e) => setForm({ ...form, rate_to_base: e.target.value })}
          />
        </Field>
        <Field label="Fecha">
          <input
            className="input"
            type="date"
            required
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
          />
        </Field>
        <button className="btn btn-primary" disabled={add.isPending}>
          Agregar
        </button>
      </form>
      <ErrorText error={add.error ?? refresh.error} />
    </Card>
  );
}

function AccessCard() {
  const { data: settings } = useSettings();
  const { data: auth } = useAuthStatus();
  const [logins, setLogins] = useState<string | null>(null);
  const [pin, setPin] = useState("");
  const save = useApiMutation("PATCH", "/api/settings");
  const pinMut = useApiMutation("PUT", "/api/settings/pin");
  const value = logins ?? settings?.allowed_logins.join(", ") ?? "";

  return (
    <Card
      title="Acceso remoto (Tailscale)"
      subtitle="Quién puede abrir el dashboard desde otros dispositivos"
    >
      <p className="mb-3 text-sm text-ink-2">
        Estás entrando desde{" "}
        <strong>{auth?.is_local ? "este equipo" : `Tailscale como ${auth?.identity}`}</strong>.
      </p>
      <Field
        label="Usuarios de Tailscale permitidos"
        hint="Separados por coma. Vacío = cualquier usuario de tu tailnet."
      >
        <input
          className="input"
          value={value}
          onChange={(e) => setLogins(e.target.value)}
          placeholder="tu@correo.com"
        />
      </Field>
      <button
        className="btn mt-2"
        onClick={() =>
          save.mutate({
            allowed_logins: value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          })
        }
      >
        Guardar usuarios
      </button>

      <hr className="my-4 border-line" />
      <Field
        label={settings?.pin_enabled ? "Cambiar PIN" : "Activar PIN"}
        hint="Se pide solo en accesos remotos, una vez cada 30 días por dispositivo."
      >
        <input
          className="input tabular"
          inputMode="numeric"
          maxLength={12}
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
          placeholder="4 a 12 dígitos"
        />
      </Field>
      <div className="mt-2 flex gap-2">
        <button
          className="btn"
          disabled={pin.length < 4}
          onClick={() => pinMut.mutate({ pin }, { onSuccess: () => setPin("") })}
        >
          Guardar PIN
        </button>
        {settings?.pin_enabled && (
          <button className="btn btn-danger" onClick={() => pinMut.mutate({ pin: null })}>
            Quitar PIN
          </button>
        )}
      </div>
      <ErrorText error={save.error ?? pinMut.error} />
    </Card>
  );
}

function PreferencesCard() {
  const { data: settings } = useSettings();
  const [currencies, setCurrencies] = useState<string | null>(null);
  const [ret, setRet] = useState<string | null>(null);
  const save = useApiMutation("PATCH", "/api/settings");
  const curValue = currencies ?? settings?.currencies.join(", ") ?? "";
  const retValue = ret ?? String(settings?.projection_annual_return_pct ?? "");
  return (
    <Card title="Preferencias">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Monedas que usas"
          hint="Aparecen en los formularios y se actualizan automáticamente"
        >
          <input
            className="input uppercase"
            value={curValue}
            onChange={(e) => setCurrencies(e.target.value)}
          />
        </Field>
        <Field label="Rendimiento anual para proyecciones (%)">
          <input
            className="input"
            type="number"
            step="0.1"
            value={retValue}
            onChange={(e) => setRet(e.target.value)}
          />
        </Field>
      </div>
      <button
        className="btn mt-3"
        onClick={() =>
          save.mutate({
            currencies: curValue
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
            projection_annual_return_pct: Number(retValue),
          })
        }
      >
        Guardar preferencias
      </button>
      <ErrorText error={save.error} />
      <p className="mt-4 text-xs text-ink-3">
        Versión {settings?.version} · Datos en{" "}
        <code className="break-all">{settings?.data_dir}</code>
      </p>
    </Card>
  );
}

function BackupCard() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const exportJson = async () => {
    const data = await api<unknown>("/api/backup/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `mamoney-${todayIso()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const importJson = async (file: File) => {
    setError(null);
    if (
      !confirm(
        "Esto reemplaza TODOS tus datos por los del archivo. Antes se guarda un respaldo automático. ¿Continuar?",
      )
    )
      return;
    try {
      const payload = JSON.parse(await file.text());
      const counts = await api<Record<string, number>>("/api/backup/import", {
        method: "POST",
        json: payload,
      });
      setStatus(`Importado: ${Object.values(counts).reduce((a, b) => a + b, 0)} registros.`);
      await qc.invalidateQueries();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <Card
      title="Respaldo y restauración"
      subtitle="Tus datos viven solo en este equipo: respáldalos seguido."
    >
      <div className="flex flex-wrap gap-2">
        <a className="btn" href="/api/backup/db">
          <Download size={14} /> Base de datos (.db)
        </a>
        <button className="btn" onClick={exportJson}>
          <Download size={14} /> Exportar JSON
        </button>
        <button className="btn" onClick={() => fileRef.current?.click()}>
          <Upload size={14} /> Importar JSON
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) importJson(f);
            e.target.value = "";
          }}
        />
      </div>
      {status && <p className="mt-3 text-sm text-good">{status}</p>}
      <ErrorText error={error} />
    </Card>
  );
}
