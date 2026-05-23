"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { StepReplay } from "@/components/StepReplay";

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: run, isLoading, error } = useQuery({
    queryKey: ["application", id],
    queryFn: () => api.getApplication(id),
    // Poll while the run is still in progress
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 3000 : false;
    },
  });

  const submit = useMutation({
    mutationFn: () => api.submitApplication(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["application", id] }),
  });

  if (isLoading) {
    return <div className="text-sm text-gray-500">Loading…</div>;
  }
  if (error) {
    return <div className="text-sm text-red-500">Failed to load: {(error as Error).message}</div>;
  }
  if (!run) return null;

  const isActive = run.status === "queued" || run.status === "running";

  return (
    <div>
      <button
        onClick={() => router.push("/dashboard")}
        className="text-sm text-gray-500 hover:text-gray-800 mb-4 inline-flex items-center gap-1"
      >
        ← Back
      </button>

      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-400 font-mono mb-1">{run.id}</p>
            <div className="flex items-center gap-3">
              <StatusBadge status={run.status} />
              {isActive && (
                <span className="text-xs text-yellow-600 animate-pulse">Processing…</span>
              )}
            </div>
          </div>
          <div className="text-right text-sm text-gray-500">
            <p>Started {new Date(run.created_at).toLocaleString()}</p>
            {run.submitted_at && (
              <p className="text-green-600 font-medium mt-0.5">
                Submitted {new Date(run.submitted_at).toLocaleString()}
              </p>
            )}
          </div>
        </div>

        {/* Review gate */}
        {run.status === "review" && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-sm text-gray-600 mb-3">
              Review the application below. Once you approve, it will be submitted.
            </p>
            <button
              onClick={() => submit.mutate()}
              disabled={submit.isPending}
              className="bg-green-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {submit.isPending ? "Submitting…" : "Approve & Submit"}
            </button>
            {submit.isError && (
              <p className="text-sm text-red-500 mt-2">{(submit.error as Error).message}</p>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Cover letter */}
        {run.cover_letter && (
          <section>
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
              Cover Letter
            </h2>
            <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {run.cover_letter}
            </div>
          </section>
        )}

        {/* Rewritten bullets */}
        {run.bullets.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
              Tailored Bullets
            </h2>
            <ul className="bg-white rounded-xl border border-gray-200 p-5 space-y-2">
              {run.bullets.map((b, i) => (
                <li key={i} className="flex gap-2 text-sm text-gray-700">
                  <span className="text-indigo-400 mt-0.5">•</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* Step replay */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
          Agent Steps ({run.steps.length})
        </h2>
        <StepReplay steps={run.steps} />
      </section>
    </div>
  );
}
