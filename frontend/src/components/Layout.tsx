import clsx from "clsx";
import {
  BarChart3,
  CalendarClock,
  LayoutDashboard,
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

const NAV = [
  { to: "/", label: "Resumen", icon: LayoutDashboard },
  { to: "/patrimonio", label: "Patrimonio", icon: Wallet },
  { to: "/ingresos", label: "Ingresos", icon: TrendingUp },
  { to: "/gastos", label: "Gastos fijos", icon: CalendarClock },
  { to: "/analisis", label: "Análisis", icon: BarChart3 },
  { to: "/ajustes", label: "Ajustes", icon: Settings },
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

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span className="text-lg font-semibold tracking-tight">Mamoney</span>
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

      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface/95 px-4 py-3 backdrop-blur md:hidden">
        <Logo />
        <ThemeToggle />
      </header>

      <main className="mx-auto w-full max-w-7xl px-4 pt-6 pb-28 sm:px-6 md:pb-10 lg:px-8">
        <UpdateBanner />
        <Outlet />
      </main>

      <nav
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-6 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Navegación principal"
      >
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium",
                isActive ? "text-accent" : "text-ink-3",
              )
            }
          >
            <Icon size={20} />
            <span className="truncate">{label.split(" ")[0]}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
