"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Plus, ArrowUpRight, Briefcase, CheckCircle, Clock, TrendingUp, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { MOCK_APPLICATIONS } from "@/lib/mock-data";
import { StatusBadge } from "@/components/StatusBadge";
import { FitScoreInline } from "@/components/FitScorePill";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, timeAgo } from "@/lib/utils";

const DEFAULT_USER = "user-123";

const ATS_BADGE: Record<string, { label: string; variant: "blue" | "violet" | "amber" | "default" | "indigo" }> = {
  greenhouse: { label: "Greenhouse", variant: "blue" },
  lever:      { label: "Lever",      variant: "violet" },
  workday:    { label: "Workday",    variant: "amber" },
  ashby:      { label: "Ashby",      variant: "indigo" },
  unknown:    { label: "Custom",     variant: "default" },
};

function StatCard({
  label,
  value,
  icon: Icon,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</span>
        <Icon className="h-4 w-4 text-gray-300" />
      </div>
      <p className={cn("text-2xl font-semibold text-gray-900 tabular-nums", accent)}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function RowSkeleton() {
  return (
    <tr>
      <td className="px-4 py-3"><Skeleton className="h-3 w-20" /></td>
      <td className="px-4 py-3">
        <Skeleton className="h-3.5 w-32 mb-1.5" />
        <Skeleton className="h-3 w-20" />
      </td>
      <td className="px-4 py-3"><Skeleton className="h-3 w-10" /></td>
      <td className="px-4 py-3"><Skeleton className="h-3 w-16" /></td>
      <td className="px-4 py-3"><Skeleton className="h-3 w-12" /></td>
    </tr>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="h-12 w-12 rounded-xl bg-indigo-50 flex items-center justify-center mb-4">
        <Briefcase className="h-6 w-6 text-indigo-400" />
      </div>
      <p className="text-sm font-medium text-gray-700 mb-1">No applications yet</p>
      <p className="text-xs text-gray-400 mb-5">Paste a job URL above to let the agent handle it</p>
      <Button size="sm" variant="outline" onClick={onAdd}>
        <Plus className="h-3.5 w-3.5" /> Add first application
      </Button>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [jobUrl, setJobUrl] = useState("");
  const [urlError, setUrlError] = useState("");
  const [showInput, setShowInput] = useState(false);

  const { data: applications, isLoading } = useQuery({
    queryKey: ["applications", DEFAULT_USER],
    queryFn: () => api.listApplications(DEFAULT_USER),
    refetchInterval: 5000,
  });

  const trigger = useMutation({
    mutationFn: (url: string) => api.triggerApplication(DEFAULT_USER, url),
    onSuccess: (data) => {
      setJobUrl("");
      setShowInput(false);
      setUrlError("");
      qc.invalidateQueries({ queryKey: ["applications"] });
      router.push(`/applications/${data.run_id}`);
    },
    onError: (err: Error) => setUrlError(err.message),
  });

  const rows = applications?.length ? applications : MOCK_APPLICATIONS;

  const total = rows.length;
  const inReview = rows.filter((a) => a.status === "review").length;
  const submitted = rows.filter((a) => a.status === "submitted").length;
  const avgFit = rows.length
    ? Math.round(rows.reduce((s, a) => s + (("fit_score" in a ? a.fit_score : 0) ?? 0), 0) / rows.length)
    : 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jobUrl.trim()) return;
    try { new URL(jobUrl.trim()); }
    catch { setUrlError("Enter a valid job URL"); return; }
    setUrlError("");
    trigger.mutate(jobUrl.trim());
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Applications</h1>
          <p className="text-xs text-gray-400 mt-0.5">Vision-gated · human-reviewed · quality-first</p>
        </div>
        <Button size="sm" onClick={() => setShowInput(!showInput)}>
          <Plus className="h-3.5 w-3.5" />
          New application
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-6 py-5 space-y-5">
          {/* URL input */}
          {showInput && (
            <form onSubmit={handleSubmit} className="animate-fade-in">
              <div className="flex gap-2">
                <input
                  type="url"
                  autoFocus
                  placeholder="https://boards.greenhouse.io/company/jobs/123"
                  value={jobUrl}
                  onChange={(e) => { setJobUrl(e.target.value); setUrlError(""); }}
                  className="flex-1 h-9 rounded-md border border-gray-300 bg-white px-3 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <Button type="submit" size="sm" disabled={trigger.isPending}>
                  {trigger.isPending ? "Queuing…" : "Apply"}
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowInput(false)}>
                  Cancel
                </Button>
              </div>
              {urlError && (
                <div className="flex items-center gap-1.5 mt-2 text-xs text-red-600">
                  <AlertCircle className="h-3 w-3" />
                  {urlError}
                </div>
              )}
              <p className="mt-2 text-xs text-gray-400">
                Paste a direct ATS link — Greenhouse, Lever, Ashby, or Workday
              </p>
            </form>
          )}

          {/* Stats */}
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="Total" value={total} icon={Briefcase} />
            <StatCard
              label="In review"
              value={inReview}
              icon={Clock}
              sub={inReview > 0 ? "Waiting for approval" : undefined}
              accent={inReview > 0 ? "text-violet-600" : undefined}
            />
            <StatCard
              label="Submitted"
              value={submitted}
              icon={CheckCircle}
              accent={submitted > 0 ? "text-emerald-600" : undefined}
            />
            <StatCard
              label="Avg fit score"
              value={`${avgFit}%`}
              icon={TrendingUp}
              sub="Across all applications"
              accent={avgFit >= 80 ? "text-emerald-600" : avgFit >= 60 ? "text-amber-600" : "text-red-500"}
            />
          </div>

          {/* Table */}
          <div className="rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide w-28">Status</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Role</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide w-28">Fit score</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide w-24">ATS</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide w-24">Applied</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {isLoading
                  ? Array.from({ length: 4 }).map((_, i) => <RowSkeleton key={i} />)
                  : rows.length === 0
                  ? (
                    <tr>
                      <td colSpan={6}>
                        <EmptyState onAdd={() => setShowInput(true)} />
                      </td>
                    </tr>
                  )
                  : rows.map((app) => {
                    const isMock = "company" in app;
                    const company = isMock ? (app as typeof MOCK_APPLICATIONS[0]).company : null;
                    type ListItem = { id: string; status: string; job_title: string | null; fit_score: number | null; created_at: string };
                    const title = isMock
                      ? (app as typeof MOCK_APPLICATIONS[0]).title
                      : (app as ListItem).job_title;
                    const fitScore = isMock
                      ? (app as typeof MOCK_APPLICATIONS[0]).fit_score
                      : (app as ListItem).fit_score;
                    const atsType = isMock
                      ? (app as typeof MOCK_APPLICATIONS[0]).ats_type
                      : "unknown";
                    const atsCfg = ATS_BADGE[atsType] ?? ATS_BADGE.unknown;

                    return (
                      <tr
                        key={app.id}
                        className="group hover:bg-gray-50 cursor-pointer transition-colors"
                        onClick={() => router.push(`/applications/${app.id}`)}
                      >
                        <td className="px-4 py-3">
                          <StatusBadge status={app.status} />
                        </td>
                        <td className="px-4 py-3 min-w-0">
                          <p className="font-medium text-gray-900 truncate">
                            {title ?? "Untitled Role"}
                          </p>
                          {company && (
                            <p className="text-xs text-gray-400 mt-0.5">{company}</p>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {fitScore != null ? (
                            <FitScoreInline score={fitScore} />
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={atsCfg.variant}>{atsCfg.label}</Badge>
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-400 tabular-nums">
                          {timeAgo(app.created_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <ArrowUpRight className="h-3.5 w-3.5 text-gray-300 group-hover:text-gray-500 transition-colors" />
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
