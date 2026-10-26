import type { AssetType, ExpenseCategory, Frequency, IncomeType, Liquidity } from "../lib/labels";

export interface Asset {
  id: number;
  name: string;
  type: AssetType;
  is_liability: boolean;
  currency: string;
  liquidity: Liquidity;
  institution: string | null;
  notes: string | null;
  archived: boolean;
  tracks_positions: boolean;
}

export interface AssetRow extends Omit<Asset, "notes"> {
  value: number | null;
  value_base: number;
  last_valuation: string | null;
  change_pct: number | null;
}

export interface Valuation {
  id: number;
  asset_id: number;
  date: string;
  value: number;
  notes: string | null;
}

export interface IncomeSource {
  id: number;
  name: string;
  type: IncomeType;
  is_passive: boolean;
  currency: string;
  frequency: Frequency;
  expected_amount: number;
  asset_id: number | null;
  active: boolean;
  notes: string | null;
}

export interface IncomeSourceRow {
  id: number;
  name: string;
  type: IncomeType;
  is_passive: boolean;
  active: boolean;
  currency: string;
  frequency: Frequency;
  expected_amount: number;
  expected_monthly_base: number;
  actual_monthly_base: number;
}

export interface IncomeEntry {
  id: number;
  source_id: number;
  date: string;
  gross_amount: number;
  tax_withheld: number;
  net_amount: number;
  notes: string | null;
}

export interface FixedExpense {
  id: number;
  name: string;
  category: ExpenseCategory;
  amount: number;
  currency: string;
  frequency: Frequency;
  due_day: number;
  start_date: string;
  end_date: string | null;
  payment_asset_id: number | null;
  active: boolean;
  notes: string | null;
}

export interface UpcomingPayment {
  expense_id: number;
  name: string;
  category: ExpenseCategory;
  due_date: string;
  amount: number;
  currency: string;
  amount_base: number;
  status: "paid" | "pending" | "overdue";
  payment_id: number | null;
}

export interface Summary {
  base_currency: string;
  as_of: string;
  assets: number;
  liabilities: number;
  net_worth: number;
  liquid_assets: number;
  monthly_income: number;
  passive_monthly_income: number;
  income_this_month: number;
  monthly_fixed_expenses: number;
  free_cash_flow: number;
  savings_rate_pct: number | null;
  passive_coverage_pct: number | null;
  runway_months: number | null;
  debt_to_assets_pct: number | null;
  income_concentration_pct: number | null;
  missing_rates: string[];
}

export interface NetWorthPoint {
  date: string;
  assets: number;
  liabilities: number;
  net_worth: number;
}

export interface KeyValue {
  key: string;
  value: number;
}

export interface Distribution {
  by_type: KeyValue[];
  by_currency: KeyValue[];
  by_liquidity: KeyValue[];
}

export interface IncomeMonth {
  month: string;
  total: number;
  by_source: Record<string, number>;
}

export interface Projection {
  annual_return_pct: number;
  monthly_savings: number;
  points: { year: number; value: number; contributed: number }[];
}

export interface Performance {
  id: number;
  name: string;
  since: string;
  start_value_base: number;
  current_value_base: number;
  income_base: number;
  gain_base: number;
  total_return_pct: number | null;
  annualized_return_pct: number | null;
}

export interface FxLatest {
  currency: string;
  rate_to_base: number | null;
  date: string | null;
  source: string | null;
}

export interface Settings {
  base_currency: string;
  currencies: string[];
  allowed_logins: string[];
  projection_annual_return_pct: number;
  pin_enabled: boolean;
  auto_update_check: boolean;
  data_dir: string;
  version: string;
}

export interface AuthStatus {
  authorized: boolean;
  reason: string;
  is_local: boolean;
  identity: string | null;
  pin_enabled: boolean;
}

export interface ReleaseInfo {
  version: string;
  tag: string;
  name: string;
  notes: string;
  published_at: string | null;
  html_url: string;
  zip_url: string | null;
  zip_name: string | null;
  zip_size: number | null;
  sha256_url: string | null;
}

export interface UpdateStatus {
  current: string;
  latest: ReleaseInfo | null;
  available: boolean;
  checked_at: string | null;
  error: string | null;
  can_install: boolean;
  installing: boolean;
}

export interface TailscaleStatus {
  installed: boolean;
  running: boolean;
  published: boolean;
  https_enabled: boolean;
  url: string | null;
  hostname: string | null;
  login: string | null;
  error: string | null;
}

export type SecurityKind = "stock" | "etf" | "crypto" | "fund" | "other";

export interface SecuritySearchResult {
  symbol: string;
  name: string | null;
  kind: SecurityKind;
  exchange: string | null;
}

export interface PositionRow {
  account_id: number;
  account: string;
  security_id: number;
  symbol: string;
  name: string | null;
  kind: SecurityKind;
  currency: string;
  quantity: number;
  avg_cost: number;
  cost: number;
  price: number | null;
  price_at: string | null;
  value: number | null;
  gain: number | null;
  gain_pct: number | null;
  realized: number;
  value_base: number;
  weight_pct: number | null;
}

export interface PositionsReport {
  positions: PositionRow[];
  value_base: number;
  cost_base: number;
  unrealized_base: number;
  unrealized_pct: number | null;
  realized_base: number;
  missing_rates: string[];
}

export interface TradeRow {
  id: number;
  asset_id: number;
  security_id: number;
  date: string;
  side: "buy" | "sell" | "balance";
  quantity: number;
  price: number | null;
  fee: number;
  notes: string | null;
  symbol: string;
  security_name: string | null;
  currency: string;
  account: string;
  total: number | null;
}
