import type { HTMLAttributes } from "react";
import { cn } from "./utils";

export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <article
      className={cn(
        "rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm",
        className,
      )}
      {...props}
    />
  );
}
