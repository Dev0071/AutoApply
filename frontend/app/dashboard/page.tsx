"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

const DEFAULT_USER = "user-123";

export default function DashboardPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [jobUrl, setJobUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: applications, isLoading } = useQuery({
    queryKey: ["applications", DEFAULT_USER],
    queryFn: () => api.listApplications(DEFAULT_USER),
    refetchInterval: 5000,
  });

  const trigger = useMutation({
    mutationFn: (url: string) => api.triggerApplication(DEFAULT_USER, url),
    onSuccess: (data) => {
      setJobUrl("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["applications"] });
      router.push(`/applications/${data.run_id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jobUrl.trim()) return;
    trigger.mutate(jobUrl.trim());
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Applications</h1>
        <a href="/profile" className="text-sm text-indigo-600 hover:underline">Edit profile →</a>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 mb-8">
        <input
          type="url"
          placeholder="Paste a job URL (Greenhouse, Lever, Workday…)"
          value={jobUrl}
          onChange={(e) => setJobUrl(e.target.value)}
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          required
        />
        <button
          type="submit"
          disabled={trigger.isPending}
          className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {trigger.isPending ? "Queuing…" : "Apply"}
        </button>
      </form>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-sm text-gray-500">Loading applications…</div>
      )}

      {applications && applications.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No applications yet.</p>
          <p className="text-sm mt-1">Paste a job URL above to get started.</p>
        </div>
      )}

      <div className="space-y-3">
        {applications?.map((app) => (
          <div
            key={app.id}
            onClick={() => router.push(`/applications/${app.id}`)}
            className="bg-white rounded-xl border border-gray-200 px-5 py-4 cursor-pointer hover:border-indigo-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="font-medium text-gray-900 truncate">
                  {app.job_title ?? "Untitled Role"}
                  {app.company && <span className="text-gray-500 font-normal"> · {app.company}</span>}
                </p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">{app.job_url}</p>
              </div>
              <div className="flex items-center gap-3 ml-4 shrink-0">
                {app.fit_score !== null && (
                  <span className="text-sm font-semibold text-indigo-600">{app.fit_score}%</span>
                )}
                <StatusBadge status={app.status} />
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              {new Date(app.created_at).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
