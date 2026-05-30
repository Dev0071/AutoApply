import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset",
  {
    variants: {
      variant: {
        default: "bg-gray-50 text-gray-700 ring-gray-200",
        blue: "bg-blue-50 text-blue-700 ring-blue-200",
        amber: "bg-amber-50 text-amber-700 ring-amber-200",
        violet: "bg-violet-50 text-violet-700 ring-violet-200",
        emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
        red: "bg-red-50 text-red-700 ring-red-200",
        indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
        outline: "bg-white text-gray-600 ring-gray-300",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
