import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<string, { dot: string; label: string; text: string }> = {
  pending:   { dot: "bg-gray-400",              label: "Pending",   text: "text-gray-500"   },
  queued:    { dot: "bg-blue-500",              label: "Queued",    text: "text-blue-600"   },
  running:   { dot: "bg-amber-500 animate-pulse", label: "Running", text: "text-amber-600"  },
  review:    { dot: "bg-violet-500",            label: "Review",    text: "text-violet-600" },
  submitted: { dot: "bg-emerald-500",           label: "Submitted", text: "text-emerald-600"},
  failed:    { dot: "bg-red-500",               label: "Failed",    text: "text-red-600"    },
};

interface StatusBadgeProps {
  status: string;
  showDot?: boolean;
  className?: string;
}

export function StatusBadge({ status, showDot = true, className }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", cfg.text, className)}>
      {showDot && (
        <span className={cn("inline-block h-1.5 w-1.5 rounded-full shrink-0", cfg.dot)} />
      )}
      {cfg.label}
    </span>
  );
}
