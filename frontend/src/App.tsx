import { useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { api } from "./api/client";
import { useAuthStatus } from "./api/hooks";
import { Layout } from "./components/Layout";
import { ErrorText } from "./components/ui";
import { AnalysisPage } from "./pages/Analysis";
import { AssetsPage } from "./pages/Assets";
import { DashboardPage } from "./pages/Dashboard";
import { ExpensesPage } from "./pages/Expenses";
import { IncomePage } from "./pages/Income";
import { SettingsPage } from "./pages/Settings";

function PinGate() {
  const qc = useQueryClient();
  const [pin, setPin] = useState("");
  const [error, setError] = useState<unknown>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api("/api/auth/pin", { method: "POST", json: { pin } });
      await qc.invalidateQueries();
    } catch (err) {
      setError(err);
    }
  };
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-xs space-y-4 rounded-xl border border-line bg-surface p-6"
      >
        <div className="flex items-center gap-2">
          <Lock size={18} />
          <h1 className="text-lg font-semibold">Mamoney</h1>
        </div>
        <p className="text-sm text-ink-2">Escribe tu PIN para acceder desde este dispositivo.</p>
        <input
          className="input tabular text-center text-xl tracking-[0.4em]"
          inputMode="numeric"
          autoComplete="current-password"
          autoFocus
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
          maxLength={12}
          aria-label="PIN"
        />
        <ErrorText error={error} />
        <button className="btn btn-primary w-full justify-center" disabled={pin.length < 4}>
          Entrar
        </button>
      </form>
    </div>
  );
}

function Blocked({ reason }: { reason: string }) {
  return (
    <div className="grid min-h-screen place-items-center px-4 text-center">
      <div>
        <h1 className="text-lg font-semibold">Acceso no autorizado</h1>
        <p className="mt-2 text-sm text-ink-2">{reason}</p>
      </div>
    </div>
  );
}

export default function App() {
  const qc = useQueryClient();
  const { data: auth, isLoading } = useAuthStatus();

  useEffect(() => {
    const onPin = () => qc.invalidateQueries({ queryKey: ["auth"] });
    window.addEventListener("mamoney:pin-required", onPin);
    return () => window.removeEventListener("mamoney:pin-required", onPin);
  }, [qc]);

  if (isLoading) return null;
  if (auth && !auth.authorized) {
    return auth.reason === "pin_required" ? <PinGate /> : <Blocked reason={auth.reason} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="patrimonio" element={<AssetsPage />} />
          <Route path="ingresos" element={<IncomePage />} />
          <Route path="gastos" element={<ExpensesPage />} />
          <Route path="analisis" element={<AnalysisPage />} />
          <Route path="ajustes" element={<SettingsPage />} />
          <Route path="*" element={<DashboardPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
