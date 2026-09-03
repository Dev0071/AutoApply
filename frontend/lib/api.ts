const BASE = "/api";

export interface ApplicationListItem {
  id: string;
  status: string;
  job_url: string | null;
  job_title: string | null;
  company: string | null;
  fit_score: number | null;
  created_at: string;
}

export interface StepUsage {
  model?: string;
  stage?: string;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
}

export interface StepLog {
  step_number?: number;
  action?: string;
  x?: number;
  y?: number;
  value?: string;
  field_name?: string;
  reasoning?: string;
  confidence?: number;
  screenshot_url?: string;
  success?: boolean;
  verified?: boolean | null;
  tier?: string;
  needs_user_input?: boolean;
  usage?: StepUsage;
  timestamp?: string;
  error?: string;
  warning?: string;
}

export interface ApplicationDetail {
  id: string;
  status: string;
  job_record_id: string | null;
  steps: StepLog[];
  cover_letter: string | null;
  bullets: string[];
  total_cost_usd: number | null;
  created_at: string;
  submitted_at: string | null;
}

export interface Profile {
  id?: string;
  user_id: string;
  name: string;
  email: string;
  phone: string | null;
  location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  skills: string[];
  experience: Record<string, unknown>;
  fit_threshold: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  listApplications: (userId: string) =>
    request<ApplicationListItem[]>(`/applications?user_id=${userId}`),

  getApplication: (runId: string) =>
    request<ApplicationDetail>(`/applications/${runId}`),

  submitApplication: (runId: string) =>
    request<ApplicationDetail>(`/applications/${runId}/submit`, { method: "POST" }),

  getProfile: (userId: string) =>
    request<Profile>(`/profile/${userId}`),

  upsertProfile: (data: Profile) =>
    request<Profile>("/profile", { method: "POST", body: JSON.stringify(data) }),

  triggerApplication: (userId: string, jobUrl: string) =>
    request<{ run_id: string; status: string; message: string }>("/applications/trigger", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, job_url: jobUrl }),
    }),
};
