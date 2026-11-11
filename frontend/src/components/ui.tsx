import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Clock, X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { money } from "../lib/format";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3 sm:mb-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-ink-2 sm:mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("rounded-xl border border-line bg-surface p-4 sm:p-5", className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-base font-semibold">{title}</h2>}
            {subtitle && <p className="text-xs text-ink-3">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "good" | "critical";
}) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-surface p-3 sm:p-4">
      <p className="truncate text-[11px] font-medium uppercase tracking-wide text-ink-3 sm:text-xs">
        {label}
      </p>
      <p
        className={clsx(
          "tabular mt-1 truncate text-[15px] font-semibold min-[360px]:text-lg sm:text-2xl",
          tone === "good" && "text-good",
          tone === "critical" && "text-critical",
        )}
        title={value}
      >
        {value}
      </p>
      {hint && <p className="mt-1 line-clamp-2 text-[11px] text-ink-2 sm:text-xs">{hint}</p>}
    </div>
  );
}

/** Barra de avance; se pinta en tono crítico al pasar del 100 %. */
export function ProgressBar({
  value,
  max,
  label,
  color = "var(--series-1)",
}: {
  value: number;
  max: number;
  label: string;
  color?: string;
}) {
  const ratio = max > 0 ? value / max : 0;
  return (
    <div
      className="h-2 rounded-full bg-surface-2"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(ratio * 100)}
    >
      <div
        className="h-2 rounded-full"
        style={{
          width: `${Math.min(ratio, 1) * 100}%`,
          background: ratio > 1 ? "var(--critical)" : color,
        }}
      />
    </div>
  );
}

/** Mosaico con barra de avance: "X de Y". */
export function ProgressTile({
  label,
  value,
  max,
  hint,
  color,
}: {
  label: string;
  value: number;
  max: number | null;
  hint?: string;
  color?: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-surface p-3 sm:p-4">
      <p className="truncate text-[11px] font-medium uppercase tracking-wide text-ink-3 sm:text-xs">
        {label}
      </p>
      <p className="tabular mt-1 truncate text-[15px] font-semibold min-[360px]:text-lg sm:text-2xl">
        {money(value)}
      </p>
      {max ? (
        <>
          <div className="mt-2">
            <ProgressBar value={value} max={max} label={label} color={color} />
          </div>
          <p className="mt-1 line-clamp-2 text-[11px] text-ink-2 sm:text-xs">
            de {money(max)} · {Math.round((value / max) * 100)} %{hint ? ` · ${hint}` : ""}
          </p>
        </>
      ) : (
        hint && <p className="mt-1 line-clamp-2 text-[11px] text-ink-2 sm:text-xs">{hint}</p>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-4 py-10 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
  wide,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className={clsx(
        // Teléfono: hoja desde abajo a todo el ancho; desde sm, ventana centrada.
        "mx-0 mt-auto mb-0 max-h-[90dvh] w-full max-w-none overflow-y-auto rounded-t-2xl border border-line bg-surface p-0 text-ink backdrop:bg-black/40",
        "sm:m-auto sm:w-[calc(100%-2rem)] sm:rounded-xl",
        wide ? "sm:max-w-3xl" : "sm:max-w-lg",
      )}
    >
      {open && (
        <div className="p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] sm:p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{title}</h2>
            <button className="btn btn-sm" onClick={onClose} aria-label="Cerrar">
              <X size={16} />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

export function Field({
  label,
  children,
  hint,
  className,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  className?: string;
}) {
  return (
    <label className={clsx("block text-sm", className)}>
      <span className="mb-1 block font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-3">{hint}</span>}
    </label>
  );
}

export function SelectOptions({ options }: { options: Record<string, string> }) {
  return (
    <>
      {Object.entries(options).map(([value, text]) => (
        <option key={value} value={value}>
          {text}
        </option>
      ))}
    </>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-critical">
      {error instanceof Error ? error.message : String(error)}
    </p>
  );
}

const STATUS = {
  paid: { text: "Pagado", icon: CheckCircle2, color: "var(--good)" },
  pending: { text: "Pendiente", icon: Clock, color: "var(--text-3)" },
  overdue: { text: "Vencido", icon: AlertTriangle, color: "var(--critical)" },
} as const;

/** Estado con icono + texto: el color nunca va solo. */
export function StatusBadge({ status }: { status: keyof typeof STATUS }) {
  const { text, icon: Icon, color } = STATUS[status];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-ink-2">
      <Icon size={14} color={color} aria-hidden />
      {text}
    </span>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-lg border border-line p-0.5"
    >
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-md px-2.5 py-1 text-xs font-medium",
            o.value === value ? "bg-accent-soft text-ink" : "text-ink-3 hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
