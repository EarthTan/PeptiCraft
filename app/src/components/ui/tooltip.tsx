/**
 * A short explanation that appears beside a term the reader may not know.
 *
 * The trigger is a small icon rather than the term itself, so adding an explanation never
 * moves the term or changes its size, weight or colour - the surrounding layout keeps the
 * shape it had. The wording lives in `lib/glossary`, next to the terms it describes.
 */
import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import { Info } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type Side = "top" | "right" | "bottom" | "left"

export function Tooltip({
  content,
  children,
  side = "top",
  align = "center",
  className,
}: {
  content: ReactNode
  children: ReactNode
  side?: Side
  align?: "start" | "center" | "end"
  className?: string
}) {
  if (!content) return null

  return (
    <TooltipPrimitive.Provider delayDuration={150} skipDelayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            align={align}
            sideOffset={6}
            collisionPadding={12}
            className={cn(
              "z-50 max-w-[19rem] rounded-lg border border-gray-700 bg-gray-900 px-2.5 py-2",
              "text-[11px] leading-relaxed text-gray-100 shadow-lg",
              className,
            )}
          >
            {content}
            <TooltipPrimitive.Arrow className="fill-gray-900" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}

/**
 * The affordance itself: a small information icon that opens the explanation on hover and on
 * focus, so the explanation is reachable without a pointer.
 */
export function InfoTip({
  content,
  side = "top",
  align = "center",
  className,
}: {
  content: ReactNode
  side?: Side
  align?: "start" | "center" | "end"
  className?: string
}) {
  return (
    <Tooltip content={content} side={side} align={align}>
      <button
        type="button"
        aria-label="What this means"
        // The icon often sits inside a row that opens something on click. Reading the
        // explanation must not also open it.
        onClick={(event) => event.stopPropagation()}
        className={cn(
          "inline-flex flex-shrink-0 items-center text-gray-400 transition-colors",
          "hover:text-primary-500 focus:text-primary-500 focus:outline-none",
          className,
        )}
      >
        <Info className="w-3 h-3" aria-hidden="true" />
      </button>
    </Tooltip>
  )
}
