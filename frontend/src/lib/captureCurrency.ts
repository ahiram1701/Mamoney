import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";

const STORAGE_KEY = "mamoney.trade-currency";
const BASE = "MXN";

function remembered(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function remember(currency: string) {
  try {
    localStorage.setItem(STORAGE_KEY, currency);
  } catch {
    /* sin almacenamiento: solo no se recuerda */
  }
}

/**
 * Moneda en que se capturan precio y comisión de una operación.
 *
 * Un instrumento en USD se puede capturar en MXN (lo que cobró el bróker); el tipo de cambio
 * del día se propone y se puede corregir por el que aplicó el bróker. `factor` convierte un
 * monto del instrumento a la moneda de captura.
 */
export function useCaptureCurrency(securityCurrency: string, date: string) {
  const options = [...new Set([securityCurrency, BASE])];
  const [chosen, setChosen] = useState<string | null>(remembered);
  const currency = chosen && options.includes(chosen) ? chosen : securityCurrency;
  const foreign = currency !== securityCurrency;
  const [rateInput, setRateInput] = useState("");

  const daily = useQuery({
    queryKey: ["fx-rate", securityCurrency, currency, date],
    queryFn: () =>
      api<{ rate: number }>(
        `/api/fx/rate?currency=${securityCurrency}&to=${currency}&date=${date}`,
      ).then((r) => r.rate),
    enabled: foreign,
    retry: false,
  });

  const rate = !foreign ? 1 : rateInput !== "" ? Number(rateInput) : (daily.data ?? null);

  return {
    securityCurrency,
    currency,
    options,
    foreign,
    rate,
    dailyRate: daily.data ?? null,
    rateInput,
    setRateInput,
    setCurrency: (c: string) => {
      setChosen(c);
      remember(c);
    },
    /** Lo que se envía a la API junto con precio y comisión. */
    payload: () => ({ currency, fx_rate: foreign && rate ? rate : null }),
  };
}

export type CaptureCurrency = ReturnType<typeof useCaptureCurrency>;
