"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { StepLog } from "@/lib/api";
import { MousePointerClick, Keyboard, ChevronRight, CheckCircle2, XCircle, AlignJustify, ArrowDown } from "lucide-react";

const ACTION_ICON: Record<string, React.ElementType> = {
  click:  MousePointerClick,
  type:   Keyboard,
  select: ChevronRight,
  scroll: ArrowDown,
  done:   CheckCircle2,
  error:  XCircle,
};

const ACTION_COLOR: Record<string, string> = {
  click:  "text-blue-600 bg-blue-50",
  type:   "text-indigo-600 bg-indigo-50",
  select: "text-violet-600 bg-violet-50",
  scroll: "text-gray-500 bg-gray-50",
  done:   "text-emerald-600 bg-emerald-50",
  error:  "text-red-600 bg-red-50",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "bg-emerald-400" : pct >= 60 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-20 h-1 bg-gray-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400 tabular-nums">{pct}%</span>
    </div>
  );
}

function StepRow({ step, index, isLast }: { step: StepLog; index: number; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [imgOpen, setImgOpen] = useState(false);
  const num = (step.step_number ?? index) + 1;
  const action = step.action ?? "unknown";
  const Icon = ACTION_ICON[action] ?? AlignJustify;
  const colorCls = ACTION_COLOR[action] ?? "text-gray-500 bg-gray-50";
  const isError = action === "error" || step.success === false;

  return (
    <div className="relative">
      {/* Timeline line */}
      {!isLast && (
        <div className="absolute left-[15px] top-8 bottom-0 w-px bg-gray-100" />
      )}

      <div
        className={cn(
          "relative flex gap-3 group",
          expanded && "mb-1"
        )}
      >
        {/* Step number + icon */}
        <div className="flex flex-col items-center shrink-0">
          <div className={cn("flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold shrink-0 border", colorCls, isError && "border-red-200")}>
            <Icon className="h-3.5 w-3.5" strokeWidth={2} />
          </div>
        </div>

        {/* Content */}
        <div
          className="flex-1 min-w-0 pb-5 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-400 tabular-nums font-mono">#{num}</span>
            <span className={cn("text-xs font-semibold uppercase tracking-wide", colorCls.split(" ")[0])}>
              {action}
            </span>
            {step.field_name && (
              <span className="text-xs text-gray-500">
                {step.field_name}
              </span>
            )}
            {step.value && (
              <span className="text-xs text-gray-700 font-medium bg-gray-50 px-1.5 py-0.5 rounded border border-gray-200 truncate max-w-[180px]">
                &ldquo;{step.value}&rdquo;
              </span>
            )}
            {step.confidence !== undefined && (
              <ConfidenceBar value={step.confidence} />
            )}
            {step.screenshot_url && (
              <button
                onClick={(e) => { e.stopPropagation(); setImgOpen(true); }}
                className="text-xs text-indigo-500 hover:text-indigo-700 hover:underline ml-auto"
              >
                screenshot →
              </button>
            )}
          </div>

          {/* Reasoning — shown when expanded OR no screenshot */}
          {step.reasoning && expanded && (
            <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">
              {step.reasoning}
            </p>
          )}
          {step.error && (
            <p className="mt-1 text-xs text-red-500">{step.error}</p>
          )}
          {step.timestamp && (
            <p className="mt-1 text-xs text-gray-300 tabular-nums">
              {new Date(step.timestamp).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {/* Screenshot lightbox */}
      {imgOpen && step.screenshot_url && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-6"
          onClick={() => setImgOpen(false)}
        >
          <img
            src={step.screenshot_url}
            alt={`Step ${num}`}
            className="max-w-full max-h-full rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

export function StepReplay({ steps }: { steps: StepLog[] }) {
  if (!steps.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="h-10 w-10 rounded-full bg-gray-50 flex items-center justify-center mb-3">
          <AlignJustify className="h-4 w-4 text-gray-300" />
        </div>
        <p className="text-sm text-gray-400">No steps recorded yet</p>
        <p className="text-xs text-gray-300 mt-1">Steps will appear here while the agent is running</p>
      </div>
    );
  }

  const avgConfidence = steps
    .filter((s) => s.confidence !== undefined)
    .reduce((sum, s, _, arr) => sum + (s.confidence ?? 0) / arr.length, 0);

  return (
    <div>
      {/* Summary bar */}
      <div className="flex items-center gap-4 mb-6 pb-4 border-b border-gray-100">
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Steps</p>
          <p className="text-lg font-semibold text-gray-900">{steps.length}</p>
        </div>
        {avgConfidence > 0 && (
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Avg confidence</p>
            <p className="text-lg font-semibold text-gray-900">{Math.round(avgConfidence * 100)}%</p>
          </div>
        )}
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Successful</p>
          <p className="text-lg font-semibold text-gray-900">
            {steps.filter((s) => s.success !== false).length}/{steps.length}
          </p>
        </div>
      </div>

      {/* Timeline */}
      <div>
        {steps.map((step, i) => (
          <StepRow key={i} step={step} index={i} isLast={i === steps.length - 1} />
        ))}
      </div>
    </div>
  );
}
