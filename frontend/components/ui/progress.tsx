import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number;
  className?: string;
  trackClassName?: string;
  fillClassName?: string;
}

export function Progress({ value, className, trackClassName, fillClassName }: ProgressProps) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className={cn("relative h-1.5 overflow-hidden rounded-full bg-gray-100", trackClassName, className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-300", fillClassName ?? "bg-indigo-500")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
