const TOKEN_KEY = "naukri_auth_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event("auth-changed"));
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

type ApiOpts = {
  method?: string;
  body?: unknown;
  formData?: FormData;
  raw?: boolean;
};

export async function api<T = unknown>(path: string, opts: ApiOpts = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(path, {
    method: opts.method ?? (opts.body || opts.formData ? "POST" : "GET"),
    headers,
    body,
  });

  if (res.status === 401) {
    setToken(null);
  }

  if (opts.raw) {
    return res as unknown as T;
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// -------------------- typed helpers --------------------

export type User = {
  id: string;
  email: string;
  name: string;
  subscription: "free" | "paid" | string;
  role: "user" | "admin" | string;
  subscribed_at?: string | null;
  created_at?: string | null;
};

export type Profile = {
  naukri_email: string | null;
  resume_filename: string | null;
  resume_uploaded_at: string | null;
  schedule_mode: "once" | "twice";
  schedule_time1: string;
  schedule_time2: string | null;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
};

export type Me = {
  user: User;
  profile: Profile | null;
};

export type RunLog = {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  attempts: number;
  error: string | null;
};

export type BillingPlan = {
  id: "free" | "paid";
  name: string;
  price_inr: number;
  features: string[];
};

export type Billing = {
  subscription: string;
  subscribed_at: string | null;
  plans: BillingPlan[];
};

export type AdminUser = User & {
  has_profile: boolean;
  profile_enabled: boolean | null;
  last_run_at: string | null;
  last_status: string | null;
  run_count: number;
};

export type AdminStats = {
  total_users: number;
  paid_users: number;
  total_profiles: number;
  enabled_profiles: number;
  runs_24h: number;
  failures_24h: number;
};

export type AdminRunLog = RunLog & {
  user_id: string;
  user_email: string | null;
};
