"use client";

import { useState } from "react";
import { Shield, Bell, Sliders, Eye, ToggleLeft, ToggleRight, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

function Section({ title, icon: Icon, description, children }: {
  title: string;
  icon: React.ElementType;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-gray-400" />
          <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
        </div>
        {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
      </div>
      <div className="divide-y divide-gray-100">{children}</div>
    </div>
  );
}

function SettingRow({
  label,
  description,
  children,
  badge,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
  badge?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-gray-800">{label}</p>
          {badge && (
            <span className="text-xs bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded font-medium">
              {badge}
            </span>
          )}
        </div>
        {description && <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{description}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
        enabled ? "bg-indigo-600" : "bg-gray-200"
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform",
          enabled ? "translate-x-4.5" : "translate-x-0.5"
        )}
      />
    </button>
  );
}

export default function SettingsPage() {
  const [autoSubmit, setAutoSubmit] = useState(false);
  const [emailNotifs, setEmailNotifs] = useState(true);
  const [screenshotRetain, setScreenshotRetain] = useState(true);
  const [skipReview, setSkipReview] = useState(false);
  const [dataConsent, setDataConsent] = useState(true);

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-100">
        <h1 className="text-base font-semibold text-gray-900">Settings</h1>
        <p className="text-xs text-gray-400 mt-0.5">Agent behavior, privacy, and notification preferences</p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="max-w-2xl space-y-5">
          {/* Agent behavior */}
          <Section
            title="Agent Behavior"
            icon={Sliders}
            description="Control how the agent operates during application runs"
          >
            <SettingRow
              label="Auto-submit"
              description="Skip the review gate and submit immediately after the agent completes. Not recommended — disables human oversight."
              badge={autoSubmit ? "ON" : undefined}
            >
              <Toggle enabled={autoSubmit} onToggle={() => setAutoSubmit(!autoSubmit)} />
            </SettingRow>
            {autoSubmit && (
              <div className="mx-5 mb-4 flex gap-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2.5 text-xs text-amber-700">
                <Info className="h-3.5 w-3.5 shrink-0 mt-0.5 text-amber-500" />
                Auto-submit is on. Applications will be submitted without your review. The agent may make errors.
              </div>
            )}
            <SettingRow
              label="Skip human review"
              description="Move directly from 'running' to 'submitted' without the review step."
            >
              <Toggle enabled={skipReview} onToggle={() => setSkipReview(!skipReview)} />
            </SettingRow>
          </Section>

          {/* Review gate */}
          <Section
            title="Review Gate"
            icon={Eye}
            description="What the agent shows you before you approve submission"
          >
            <SettingRow
              label="Always show cover letter"
              description="Display the AI-generated cover letter in the review screen before submission."
            >
              <Toggle enabled={true} onToggle={() => {}} />
            </SettingRow>
            <SettingRow
              label="Show tailored bullets"
              description="Display rewritten resume bullets side-by-side with the original JD keywords."
            >
              <Toggle enabled={true} onToggle={() => {}} />
            </SettingRow>
            <SettingRow
              label="Risk flag analysis"
              description="Highlight potential mismatches between your profile and the job description."
            >
              <Toggle enabled={true} onToggle={() => {}} />
            </SettingRow>
          </Section>

          {/* Privacy & data */}
          <Section
            title="Privacy & Data"
            icon={Shield}
            description="Control how your data and screenshots are stored"
          >
            <SettingRow
              label="Retain agent screenshots"
              description="Store step-by-step screenshots in S3 for replay. Disable to skip screenshot storage (audit trail will be text-only)."
            >
              <Toggle enabled={screenshotRetain} onToggle={() => setScreenshotRetain(!screenshotRetain)} />
            </SettingRow>
            <SettingRow
              label="Allow anonymized analytics"
              description="Share anonymized fit score and success rate data to improve future agent accuracy."
            >
              <Toggle enabled={dataConsent} onToggle={() => setDataConsent(!dataConsent)} />
            </SettingRow>
            <SettingRow
              label="Delete all data"
              description="Permanently delete your profile, all application runs, and stored screenshots."
            >
              <Button variant="outline" size="sm" className="text-red-600 border-red-200 hover:bg-red-50">
                Delete account data
              </Button>
            </SettingRow>
          </Section>

          {/* Notifications */}
          <Section
            title="Notifications"
            icon={Bell}
            description="When and how to notify you about application status"
          >
            <SettingRow
              label="Email on review ready"
              description="Send an email when an application is waiting for your approval."
            >
              <Toggle enabled={emailNotifs} onToggle={() => setEmailNotifs(!emailNotifs)} />
            </SettingRow>
            <SettingRow
              label="Email on submission"
              description="Confirm by email when an application is submitted."
            >
              <Toggle enabled={false} onToggle={() => {}} />
            </SettingRow>
          </Section>

          {/* Version info */}
          <div className="text-xs text-gray-400 pt-2 pb-6 space-y-1">
            <p>AutoApply v0.1.0 · Vision-action loop active</p>
            <p>Claude Opus 4.5 (vision) · Claude Sonnet 4.6 (tailoring)</p>
          </div>
        </div>
      </div>
    </div>
  );
}
