import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Asset,
  AssetRow,
  AuthStatus,
  Distribution,
  FixedExpense,
  FxLatest,
  IncomeEntry,
  IncomeMonth,
  IncomeSource,
  IncomeSourceRow,
  NetWorthPoint,
  Performance,
  Projection,
  Settings,
  Summary,
  TailscaleStatus,
  UpcomingPayment,
  UpdateStatus,
  Valuation,
} from "./types";

const get =
  <T>(path: string) =>
  () =>
    api<T>(path);

export const useAuthStatus = () =>
  useQuery({ queryKey: ["auth"], queryFn: get<AuthStatus>("/api/auth/status") });

export const useSummary = () =>
  useQuery({ queryKey: ["summary"], queryFn: get<Summary>("/api/analytics/summary") });

export const useNetWorthHistory = (months = 24) =>
  useQuery({
    queryKey: ["net-worth", months],
    queryFn: get<NetWorthPoint[]>(`/api/analytics/net-worth-history?months=${months}`),
  });

export const useAssetRows = () =>
  useQuery({ queryKey: ["asset-rows"], queryFn: get<AssetRow[]>("/api/analytics/assets") });

export const useAssets = () =>
  useQuery({ queryKey: ["assets"], queryFn: get<Asset[]>("/api/assets") });

export const useValuations = (assetId: number | null) =>
  useQuery({
    queryKey: ["valuations", assetId],
    queryFn: get<Valuation[]>(`/api/assets/${assetId}/valuations`),
    enabled: assetId !== null,
  });

export const useDistribution = () =>
  useQuery({
    queryKey: ["distribution"],
    queryFn: get<Distribution>("/api/analytics/distribution"),
  });

export const useIncomeSources = () =>
  useQuery({ queryKey: ["income-sources"], queryFn: get<IncomeSource[]>("/api/income/sources") });

export const useIncomeSourceRows = () =>
  useQuery({
    queryKey: ["income-source-rows"],
    queryFn: get<IncomeSourceRow[]>("/api/analytics/income-sources"),
  });

export const useIncomeEntries = () =>
  useQuery({ queryKey: ["income-entries"], queryFn: get<IncomeEntry[]>("/api/income/entries") });

export const useIncomeByMonth = (months = 12) =>
  useQuery({
    queryKey: ["income-by-month", months],
    queryFn: get<IncomeMonth[]>(`/api/analytics/income-by-month?months=${months}`),
  });

export const useExpenses = () =>
  useQuery({ queryKey: ["expenses"], queryFn: get<FixedExpense[]>("/api/expenses") });

export const useExpensesByCategory = () =>
  useQuery({
    queryKey: ["expenses-by-category"],
    queryFn: get<{ key: string; value: number }[]>("/api/analytics/expenses-by-category"),
  });

export const useUpcoming = (days = 30) =>
  useQuery({
    queryKey: ["upcoming", days],
    queryFn: get<UpcomingPayment[]>(`/api/analytics/upcoming?days=${days}`),
  });

export const usePerformance = () =>
  useQuery({
    queryKey: ["performance"],
    queryFn: get<Performance[]>("/api/analytics/performance"),
  });

export const useProjection = (
  years: number,
  annualReturn: number | null,
  savings: number | null,
) => {
  const params = new URLSearchParams({ years: String(years) });
  if (annualReturn !== null) params.set("annual_return_pct", String(annualReturn));
  if (savings !== null) params.set("monthly_savings", String(savings));
  return useQuery({
    queryKey: ["projection", years, annualReturn, savings],
    queryFn: get<Projection>(`/api/analytics/projection?${params}`),
  });
};

export const useFxLatest = () =>
  useQuery({ queryKey: ["fx-latest"], queryFn: get<FxLatest[]>("/api/fx/latest") });

export const useUpdateStatus = () =>
  useQuery({
    queryKey: ["updates"],
    queryFn: get<UpdateStatus>("/api/updates"),
    staleTime: 10 * 60_000,
    refetchInterval: 30 * 60_000,
  });

export const useTailscale = () =>
  useQuery({ queryKey: ["tailscale"], queryFn: get<TailscaleStatus>("/api/tailscale") });

export const useSettings = () =>
  useQuery({ queryKey: ["settings"], queryFn: get<Settings>("/api/settings") });

type Method = "POST" | "PATCH" | "PUT" | "DELETE";

/** Mutación genérica: al terminar invalida todas las consultas (datos pequeños, un usuario). */
export function useApiMutation<TBody = unknown, TResult = unknown>(
  method: Method,
  path: string | ((body: TBody) => string),
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TBody) =>
      api<TResult>(typeof path === "function" ? path(body) : path, {
        method,
        json: method === "DELETE" ? undefined : body,
      }),
    onSuccess: () => qc.invalidateQueries(),
  });
}
