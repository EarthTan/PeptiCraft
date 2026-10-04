import * as React from "react"
import { cn } from "@/lib/utils"

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  max?: number
  indicatorClassName?: string
  size?: "sm" | "default" | "lg"
}

function Progress({ value, max = 100, className, indicatorClassName, size = "default", ...props }: ProgressProps) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100)

  const sizeClasses = {
    sm: "h-1.5",
    default: "h-2.5",
    lg: "h-4",
  }

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={cn("w-full overflow-hidden rounded-full bg-surface-muted", sizeClasses[size], className)}
      {...props}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 ease-out",
          pct >= 80 ? "bg-accent-500" : pct >= 50 ? "bg-primary-500" : "bg-amber-400",
          indicatorClassName
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export { Progress }
