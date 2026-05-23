"use client";

import { useState } from "react";
import type { StepLog } from "@/lib/api";

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

function StepCard({ step, index }: { step: StepLog; index: number }) {
  const [imgOpen, setImgOpen] = useState(false);
  const num = step.step_number ?? index;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              Step {num + 1}
            </span>
            {step.action && (
              <span className="text-xs font-medium text-indigo-600 uppercase tracking-wide">
                {step.action}
              </span>
            )}
            {step.field_name && (
              <span className="text-xs text-gray-500">→ {step.field_name}</span>
            )}
            {step.success === false && (
              <span className="text-xs text-red-500 font-medium">failed</span>
            )}
          </div>

          {step.value && (
            <p className="text-sm font-medium text-gray-800 mb-1">
              &ldquo;{step.value}&rdquo;
            </p>
          )}

          {step.reasoning && (
            <p className="text-sm text-gray-500 leading-relaxed">{step.reasoning}</p>
          )}

          {step.error && (
            <p className="text-sm text-red-500 mt-1">{step.error}</p>
          )}

          {step.confidence !== undefined && (
            <div className="mt-2">
              <ConfidenceBar value={step.confidence} />
            </div>
          )}

          {step.timestamp && (
            <p className="text-xs text-gray-400 mt-2">{new Date(step.timestamp).toLocaleTimeString()}</p>
          )}
        </div>

        {step.screenshot_url && (
          <button
            onClick={() => setImgOpen(true)}
            className="shrink-0 w-20 h-14 rounded-lg overflow-hidden border border-gray-200 hover:border-indigo-400 transition-colors"
          >
            <img src={step.screenshot_url} alt={`Step ${num + 1}`} className="w-full h-full object-cover" />
          </button>
        )}
      </div>

      {imgOpen && step.screenshot_url && (
        <div
          className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
          onClick={() => setImgOpen(false)}
        >
          <img
            src={step.screenshot_url}
            alt={`Step ${num + 1} full`}
            className="max-w-full max-h-full rounded-xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

export function StepReplay({ steps }: { steps: StepLog[] }) {
  if (!steps.length) {
    return <p className="text-sm text-gray-400 italic">No steps recorded yet.</p>;
  }
  return (
    <div className="space-y-3">
      {steps.map((step, i) => (
        <StepCard key={i} step={step} index={i} />
      ))}
    </div>
  );
}
