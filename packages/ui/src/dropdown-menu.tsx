"use client";

import { Menu } from "@base-ui/react/menu";
import type * as React from "react";
import { cn } from "./utils";

export function DropdownMenu(props: Menu.Root.Props) {
  return <Menu.Root {...props} />;
}

export function DropdownMenuTrigger(props: Menu.Trigger.Props) {
  return <Menu.Trigger data-slot="dropdown-menu-trigger" {...props} />;
}

export function DropdownMenuContent({
  className,
  sideOffset = 8,
  align = "end",
  ...props
}: Menu.Popup.Props & {
  align?: Menu.Positioner.Props["align"];
  sideOffset?: Menu.Positioner.Props["sideOffset"];
}) {
  return (
    <Menu.Portal>
      <Menu.Positioner align={align} sideOffset={sideOffset} className="z-[120] outline-none">
        <Menu.Popup
          data-slot="dropdown-menu-content"
          className={cn(
            "w-[min(25rem,calc(100vw-2rem))] origin-[var(--transform-origin)] rounded-2xl border border-border bg-popover p-1.5 text-popover-foreground shadow-2xl outline-none transition-[transform,scale,opacity] duration-150 data-ending-style:scale-95 data-ending-style:opacity-0 data-starting-style:scale-95 data-starting-style:opacity-0",
            className,
          )}
          {...props}
        />
      </Menu.Positioner>
    </Menu.Portal>
  );
}

export function DropdownMenuLinkItem({
  className,
  ...props
}: Menu.LinkItem.Props) {
  return (
    <Menu.LinkItem
      data-slot="dropdown-menu-link-item"
      className={cn(
        "flex cursor-pointer items-start gap-3 rounded-xl px-3 py-3 text-sm outline-none transition-colors data-highlighted:bg-muted",
        className,
      )}
      closeOnClick
      {...props}
    />
  );
}

export function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof Menu.Separator>) {
  return (
    <Menu.Separator
      className={cn("my-1 h-px bg-border", className)}
      {...props}
    />
  );
}
