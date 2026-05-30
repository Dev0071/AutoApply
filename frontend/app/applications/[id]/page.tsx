"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, AlertTriangle, Info, CheckCircle2, Building2,
  MapPin, ExternalLink, Hash, Clock, Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { MOCK_APPLICATIONS, type RiskFlag } from "@/lib/mock-data";
import { StatusBadge } from "@/components/StatusBadge";
import { FitScorePill } from "@/components/FitScorePill";
import { StepReplay } from "@/components/StepReplay";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn, timeAgo } from "@/lib/utils";

const ATS_BADGE: Record<string, { label: string; variant: "blue" | "violet" | "amber" | "default" | "indigo" }> = {
  greenhouse: { label: "Greenhouse", variant: "blue" },
  lever:      { label: "Lever",      variant: "violet" },
  workday:    { label: "Workday",    variant: "amber" },
  ashby:      { label: "Ashby",      variant: "indigo" },
  unknown:    { label: "Custom",     variant: "default" },
};

function RiskFlagItem({ flag }: { flag: RiskFlag }) {
  const isWarning = flag.severity === "warning";
  return (
    <div className={cn(
      "flex gap-3 rounded-lg px-3 py-2.5 text-xs",
      isWarning ? "bg-amber-50 border border-amber-200" : "bg-blue-50 border border-blue-100"
    )}>
      {isWarning
        ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
        : <Info className="h-3.5 w-3.5 text-blue-400 shrink-0 mt-0.5" />
      }
      <p className={isWarning ? "text-amber-800" : "text-blue-700"}>{flag.message}</p>
    </div>
  );
}

function KeywordChip({ word, matched }: { word: string; matched: boolean }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
      matched
        ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200"
        : "bg-gray-50 text-gray-500 ring-1 ring-inset ring-gray-200"
    )}>
      {matched && <CheckCircle2 className="h-2.5 w-2.5 shrink-0" />}
      {word}
    </span>
  );
}

function HeaderSkeleton() {
  return (
    <div className="px-6 py-5 border-b border-gray-100 space-y-2">
      <Skeleton className="h-5 w-64" />
      <Skeleton className="h-4 w-40" />
      <div className="flex gap-2 mt-3">
        <Skeleton className="h-6 w-16" />
        <Skeleton className="h-6 w-24" />
      </div>
    </div>
  );
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const isMockId = id.startsWith("mock-");
  const mockApp = MOCK_APPLICATIONS.find((a) => a.id === id);

  const { data: run, isLoading, error } = useQuery({
    queryKey: ["application", id],
    queryFn: () => api.getApplication(id),
    enabled: !isMockId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "queued" || s === "running" ? 3000 : false;
    },
  });

  const submit = useMutation({
    mutationFn: () => api.submitApplication(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["application", id] }),
  });

  const app = isMockId ? mockApp : run ? {
    ...run,
    company: null,
    title: null,
    salary: null,
    location: null,
    ats_type: "unknown",
    keywords: [],
    matched_keywords: [],
    risk_flags: [],
    cover_letter: run.cover_letter ?? "",
  } : null;

  if (!isMockId && isLoading) {
    return (
      <div className="flex flex-col h-full animate-fade-in">
        <div className="flex items-center gap-2 px-6 py-3 border-b border-gray-100">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Skeleton className="h-4 w-32" />
        </div>
        <HeaderSkeleton />
      </div>
    );
  }

  if (!app) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center py-20">
        <p className="text-sm font-medium text-gray-700 mb-1">Application not found</p>
        <p className="text-xs text-gray-400 mb-4">This run may have been deleted</p>
        <Button variant="outline" size="sm" onClick={() => router.push("/dashboard")}>
          Back to dashboard
        </Button>
      </div>
    );
  }

  const isActive = app.status === "queued" || app.status === "running";
  const atsType = "ats_type" in app ? app.ats_type : "unknown";
  const atsCfg = ATS_BADGE[atsType ?? "unknown"] ?? ATS_BADGE.unknown;
  const fitScore = "fit_score" in app ? app.fit_score : run?.steps?.[0] ? null : null;
  const resolvedFitScore = typeof fitScore === "number" ? fitScore : null;

  const keywords: string[] = "keywords" in app ? (app.keywords as string[]) : [];
  const matchedKeywords: string[] = "matched_keywords" in app ? (app.matched_keywords as string[]) : [];
  const riskFlags: RiskFlag[] = "risk_flags" in app ? (app.risk_flags as RiskFlag[]) : [];

  const isFitFailed = app.status === "failed" &&
    app.steps?.length > 0 &&
    (app.steps[0] as Record<string, unknown>).error === "fit_threshold_not_met";

  const defaultTab = app.status === "running" || app.status === "queued" ? "replay" : "review";

  return (
    <div className="flex flex-col h-full animate-fade-in">
      {/* Back nav */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-gray-100">
        <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
          <ArrowLeft className="h-3.5 w-3.5" />
        </Button>
        <span className="text-xs text-gray-400">Applications</span>
        <span className="text-xs text-gray-300">/</span>
        <span className="text-xs text-gray-600 font-medium">
          {"company" in app && app.company ? app.company : "Application"}
        </span>
      </div>

      {/* Header */}
      <div className="px-6 py-5 border-b border-gray-100">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <StatusBadge status={app.status} />
              {isActive && (
                <span className="text-xs text-amber-500 animate-pulse font-medium">Agent running…</span>
              )}
            </div>
            {"title" in app && app.title ? (
              <h1 className="text-lg font-semibold text-gray-900 leading-tight">{app.title}</h1>
            ) : (
              <h1 className="text-lg font-semibold text-gray-900 leading-tight font-mono text-sm">{id}</h1>
            )}
            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-gray-400">
              {"company" in app && app.company && (
                <span className="flex items-center gap-1">
                  <Building2 className="h-3 w-3" />
                  {app.company}
                </span>
              )}
              {"location" in app && app.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  {app.location}
                </span>
              )}
              {"salary" in app && app.salary && (
                <span className="font-medium text-gray-600">{app.salary}</span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {timeAgo(app.created_at)}
              </span>
              <Badge variant={atsCfg.variant}>{atsCfg.label}</Badge>
              {"url" in app && app.url && (
                <a
                  href={"url" in app ? `https://${app.url}` : "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-0.5 text-indigo-500 hover:text-indigo-700"
                  onClick={(e) => e.stopPropagation()}
                >
                  View job <ExternalLink className="h-2.5 w-2.5" />
                </a>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {resolvedFitScore !== null && (
              <FitScorePill score={resolvedFitScore} showBar />
            )}
            {app.status === "review" && (
              <Button variant="success" size="sm" onClick={() => submit.mutate()} disabled={submit.isPending}>
                <CheckCircle2 className="h-3.5 w-3.5" />
                {submit.isPending ? "Submitting…" : "Approve & Submit"}
              </Button>
            )}
          </div>
        </div>

        {/* Fit threshold failed banner */}
        {isFitFailed && (
          <div className="mt-4 flex items-start gap-2.5 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5">
            <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-medium text-red-700 mb-0.5">Fit score below threshold</p>
              {(app.steps[0] as Record<string, unknown>).fit_score != null ? (
                <p className="text-red-600">
                  Profile matched{" "}
                  <strong>{String((app.steps[0] as Record<string, unknown>).fit_score)}%</strong>{" "}
                  of job keywords — threshold is{" "}
                  <strong>{String((app.steps[0] as Record<string, unknown>).threshold)}%</strong>.{" "}
                  <a href="/settings" className="underline">Adjust threshold →</a>
                </p>
              ) : (
                <p className="text-red-600">
                  Profile skills did not meet the fit threshold.{" "}
                  <a href="/settings" className="underline">Adjust threshold →</a>
                </p>
              )}
            </div>
          </div>
        )}

        {submit.isError && (
          <p className="mt-2 text-xs text-red-500">{(submit.error as Error).message}</p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex-1 overflow-y-auto">
        <Tabs defaultValue={defaultTab} className="flex flex-col h-full">
          <TabsList className="px-6 bg-white shrink-0">
            <TabsTrigger value="review">Review</TabsTrigger>
            <TabsTrigger value="replay">
              Agent Replay
              {app.steps?.length > 0 && (
                <span className="ml-1.5 text-xs text-gray-400 font-normal">
                  {app.steps.length} steps
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="cover">Cover Letter</TabsTrigger>
          </TabsList>

          {/* Review tab */}
          <TabsContent value="review" className="px-6 py-5 space-y-6">
            <div className="grid grid-cols-2 gap-5">
              {/* JD Keywords */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Hash className="h-3.5 w-3.5 text-gray-400" />
                  <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    JD Keywords
                    {keywords.length > 0 && (
                      <span className="ml-1.5 text-gray-400 font-normal normal-case">
                        {matchedKeywords.length}/{keywords.length} matched
                      </span>
                    )}
                  </h2>
                </div>
                {keywords.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {keywords.map((k) => (
                      <KeywordChip key={k} word={k} matched={matchedKeywords.includes(k)} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">Keywords extracted after agent runs</p>
                )}
              </div>

              {/* Tailored bullets */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                  <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Tailored Bullets</h2>
                </div>
                {app.bullets?.length > 0 ? (
                  <ul className="space-y-2">
                    {app.bullets.map((b, i) => (
                      <li key={i} className="flex gap-2 text-xs text-gray-700 leading-relaxed">
                        <span className="text-indigo-400 shrink-0 mt-0.5">•</span>
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-400 italic">
                    {isActive ? "Generating tailored bullets…" : "No bullets generated"}
                  </p>
                )}
              </div>
            </div>

            {/* Risk flags */}
            {riskFlags.length > 0 && (
              <div>
                <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                  Risk Flags
                </h2>
                <div className="space-y-2">
                  {riskFlags.map((f) => (
                    <RiskFlagItem key={f.id} flag={f} />
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Replay tab */}
          <TabsContent value="replay" className="px-6 py-5">
            <StepReplay steps={app.steps ?? []} />
          </TabsContent>

          {/* Cover letter tab */}
          <TabsContent value="cover" className="px-6 py-5">
            {app.cover_letter ? (
              <div className="max-w-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">AI-Generated Cover Letter</h2>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigator.clipboard.writeText(app.cover_letter!)}
                  >
                    Copy
                  </Button>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-5 text-sm text-gray-700 leading-7 whitespace-pre-wrap font-serif">
                  {app.cover_letter}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Sparkles className="h-8 w-8 text-gray-200 mb-3" />
                <p className="text-sm text-gray-400">
                  {isActive ? "Cover letter is being generated…" : "No cover letter generated for this application"}
                </p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
