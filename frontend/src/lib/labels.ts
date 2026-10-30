export const ASSET_TYPES = {
  cash: "Efectivo",
  bank: "Cuenta bancaria",
  investment: "Inversión",
  crypto: "Cripto",
  retirement: "Retiro / AFORE",
  real_estate: "Inmueble",
  vehicle: "Vehículo",
  business: "Negocio",
  receivable: "Cuenta por cobrar",
  mortgage: "Hipoteca",
  credit_card: "Tarjeta de crédito",
  loan: "Préstamo",
  other: "Otro",
} as const;

export const LIABILITY_TYPES = new Set(["mortgage", "credit_card", "loan"]);

export const LIQUIDITY = {
  immediate: "Inmediata",
  short: "Corto plazo",
  long: "Largo plazo",
  illiquid: "Ilíquido",
} as const;

export const INCOME_TYPES = {
  salary: "Salario",
  freelance: "Freelance",
  business: "Negocio",
  rent: "Renta",
  dividends: "Dividendos",
  interest: "Intereses",
  royalties: "Regalías",
  sale: "Venta",
  pension: "Pensión",
  other: "Otro",
} as const;

export const PASSIVE_INCOME_TYPES = new Set([
  "rent",
  "dividends",
  "interest",
  "royalties",
  "pension",
]);

export const EXPENSE_CATEGORIES = {
  housing: "Vivienda",
  utilities: "Servicios",
  insurance: "Seguros",
  subscriptions: "Suscripciones",
  transport: "Transporte",
  education: "Educación",
  health: "Salud",
  debt: "Deudas",
  taxes: "Impuestos",
  other: "Otro",
} as const;

export const FREQUENCIES = {
  once: "Única vez",
  weekly: "Semanal",
  biweekly: "Quincenal",
  monthly: "Mensual",
  bimonthly: "Bimestral",
  quarterly: "Trimestral",
  semiannual: "Semestral",
  annual: "Anual",
} as const;

export type AssetType = keyof typeof ASSET_TYPES;
export type Liquidity = keyof typeof LIQUIDITY;
export type IncomeType = keyof typeof INCOME_TYPES;
export type ExpenseCategory = keyof typeof EXPENSE_CATEGORIES;
export type Frequency = keyof typeof FREQUENCIES;

export function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key;
}

export const SPENDING_CATEGORIES = {
  groceries: "Súper",
  restaurants: "Restaurantes y comida",
  transport: "Transporte y gasolina",
  shopping: "Compras",
  entertainment: "Entretenimiento",
  health: "Salud",
  home: "Hogar",
  travel: "Viajes",
  education: "Educación",
  personal: "Cuidado personal",
  gifts: "Regalos",
  services: "Servicios",
  other: "Otros",
} as const;
