import clsx from "clsx";
import {
  BarChart3,
  CalendarClock,
  LayoutDashboard,
  LineChart,
  Moon,
  Settings,
  Sun,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuthStatus } from "../api/hooks";
import { UpdateBanner } from "./UpdateBanner";

// `short`: nombre para la barra inferior del teléfono, donde caben 7 botones de ~53 px.
const NAV = [
  { to: "/", label: "Resumen", short: "Inicio", icon: LayoutDashboard },
  { to: "/patrimonio", label: "Patrimonio", short: "Bienes", icon: Wallet },
  { to: "/inversiones", label: "Inversiones", short: "Invers.", icon: LineChart },
  { to: "/ingresos", label: "Ingresos", short: "Ingresos", icon: TrendingUp },
  { to: "/gastos", label: "Gastos", short: "Gastos", icon: CalendarClock },
  { to: "/analisis", label: "Análisis", short: "Análisis", icon: BarChart3 },
  { to: "/ajustes", label: "Ajustes", short: "Ajustes", icon: Settings },
];

type Theme = "light" | "dark" | "system";

function readTheme(): Theme {
  try {
    return (localStorage.getItem("mamoney-theme") as Theme) || "system";
  } catch {
    return "system";
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("mamoney-theme", theme);
    } catch {
      /* almacenamiento no disponible */
    }
  }, [theme]);
  const isDark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  return (
    <button
      className="btn btn-sm"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Usar tema claro" : "Usar tema oscuro"}
    >
      {isDark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <img src="/favicon.svg" alt="" className={compact ? "size-6" : "size-7"} />
      <span className={clsx("font-semibold tracking-tight", compact ? "text-base" : "text-lg")}>
        Mamoney
      </span>
    </div>
  );
}

export function Layout() {
  const { data: auth } = useAuthStatus();
  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-surface p-4 md:flex">
        <Logo />
        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
                  isActive ? "bg-accent-soft text-ink" : "text-ink-2 hover:bg-surface-2",
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center justify-between text-xs text-ink-3">
          <span title={auth?.identity ?? undefined}>
            {auth?.is_local ? "Este equipo" : (auth?.identity ?? "Tailscale")}
          </span>
          <ThemeToggle />
        </div>
      </aside>

      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface/95 px-4 pt-[calc(env(safe-area-inset-top)+0.5rem)] pb-2 backdrop-blur md:hidden">
        <Logo compact />
        <ThemeToggle />
      </header>

      <main className="mx-auto w-full max-w-7xl px-4 pt-4 pb-28 sm:px-6 sm:pt-6 md:pb-10 lg:px-8">
        <UpdateBanner />
        <Outlet />
      </main>

      <nav
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-7 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Navegación principal"
      >
        {NAV.map(({ to, label, short, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            aria-label={label}
            className={({ isActive }) =>
              clsx(
                "relative flex min-h-12 min-w-0 flex-col items-center justify-center gap-0.5 px-0.5 pt-1.5 pb-1 text-[10px] leading-tight font-medium",
                isActive ? "text-accent" : "text-ink-3",
              )
            }
          >
            {({ isActive }) => (
              <>
                {/* La pestaña activa se marca con una barra, no solo con el color. */}
                {isActive && (
                  <span className="absolute top-0 h-0.5 w-6 rounded-full bg-accent" aria-hidden />
                )}
                <Icon size={22} aria-hidden />
                <span className="w-full truncate text-center">{short}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
