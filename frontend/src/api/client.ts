export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Enlace que el usuario debe abrir para resolver el error, si el servidor lo indica. */
    public actionUrl: string | null = null,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String(d.msg) : String(d)))
      .join("; ");
  }
  if (typeof detail === "object" && detail && "message" in detail) {
    return String(detail.message);
  }
  return "Error inesperado";
}

function actionUrlOf(detail: unknown): string | null {
  if (typeof detail === "object" && detail && "action_url" in detail && detail.action_url) {
    return String(detail.action_url);
  }
  return null;
}

export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(path, {
    credentials: "same-origin",
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* respuesta sin JSON */
    }
    if (res.status === 401 && detail === "pin_required") {
      window.dispatchEvent(new Event("mamoney:pin-required"));
    }
    throw new ApiError(res.status, describe(detail), actionUrlOf(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
