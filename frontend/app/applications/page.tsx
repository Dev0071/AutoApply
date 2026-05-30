"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Search, Filter } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { MOCK_APPLICATIONS } from "@/lib/mock-data";
import { StatusBadge } from "@/components/StatusBadge";
import { FitScoreInline } from "@/components/FitScorePill";
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

const STATUS_FILTERS = ["all", "review", "running", "queued", "submitted", "failed"] as const;

export default function ApplicationsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: applications, isLoading } = useQuery({
    queryKey: ["applications", DEFAULT_USER],
    queryFn: () => api.listApplications(DEFAULT_USER),
    refetchInterval: 5000,
  });

  const rows = applications?.length ? applications : MOCK_APPLICATIONS;

  const filtered = rows.filter((app) => {
    const isMock = "company" in app;
    const company = isMock ? (app as typeof MOCK_APPLICATIONS[0]).company : "";
    const title = isMock ? (app as typeof MOCK_APPLICATIONS[0]).title : (app as typeof rows[0] & { job_title?: string }).job_title ?? "";
    const matchesSearch = !search || [company, title].join(" ").toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || app.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div>
          <h1 className="text-base font-semibold text-gray-900">All Applications</h1>
          <p className="text-xs text-gray-400 mt-0.5">{rows.length} total</p>
        </div>
      </div>

      <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <input
            type="text"
            placeholder="Search company or role…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 w-full rounded-md border border-gray-300 bg-white pl-8 pr-3 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-1">
          <Filter className="h-3.5 w-3.5 text-gray-400" />
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-medium transition-colors capitalize",
                statusFilter === s
                  ? "bg-gray-900 text-white"
                  : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white border-b border-gray-200 z-10">
            <tr>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide w-28">Status</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Role</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide w-32">Fit score</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide w-24">ATS</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide w-28">Applied</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  <td className="px-6 py-3"><Skeleton className="h-3 w-16" /></td>
                  <td className="px-6 py-3"><Skeleton className="h-3.5 w-40" /></td>
                  <td className="px-6 py-3"><Skeleton className="h-3 w-12" /></td>
                  <td className="px-6 py-3"><Skeleton className="h-3 w-16" /></td>
                  <td className="px-6 py-3"><Skeleton className="h-3 w-10" /></td>
                </tr>
              ))
              : filtered.map((app) => {
                const isMock = "company" in app;
                const company = isMock ? (app as typeof MOCK_APPLICATIONS[0]).company : null;
                const title = isMock ? (app as typeof MOCK_APPLICATIONS[0]).title : (app as typeof rows[0] & { job_title?: string }).job_title;
                const fitScore = isMock ? (app as typeof MOCK_APPLICATIONS[0]).fit_score : (app as typeof rows[0] & { fit_score?: number }).fit_score;
                const atsType = isMock ? (app as typeof MOCK_APPLICATIONS[0]).ats_type : "unknown";
                const atsCfg = ATS_BADGE[atsType] ?? ATS_BADGE.unknown;

                return (
                  <tr
                    key={app.id}
                    className="group hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => router.push(`/applications/${app.id}`)}
                  >
                    <td className="px-6 py-3.5">
                      <StatusBadge status={app.status} />
                    </td>
                    <td className="px-6 py-3.5">
                      <p className="font-medium text-gray-900">{title ?? "Untitled Role"}</p>
                      {company && <p className="text-xs text-gray-400 mt-0.5">{company}</p>}
                    </td>
                    <td className="px-6 py-3.5">
                      {fitScore != null ? (
                        <FitScoreInline score={fitScore} />
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3.5">
                      <Badge variant={atsCfg.variant}>{atsCfg.label}</Badge>
                    </td>
                    <td className="px-6 py-3.5 text-xs text-gray-400 tabular-nums">
                      {timeAgo(app.created_at)}
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      <ArrowUpRight className="h-3.5 w-3.5 text-gray-300 group-hover:text-gray-500" />
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
