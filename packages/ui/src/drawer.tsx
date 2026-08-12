"use client";

import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer";
import type * as React from "react";
import { cn } from "./utils";

export function Drawer(props: DrawerPrimitive.Root.Props) {
  return <DrawerPrimitive.Root data-slot="drawer" {...props} />;
}

export function DrawerTrigger(props: DrawerPrimitive.Trigger.Props) {
  return <DrawerPrimitive.Trigger data-slot="drawer-trigger" {...props} />;
}

export function DrawerClose(props: DrawerPrimitive.Close.Props) {
  return <DrawerPrimitive.Close data-slot="drawer-close" {...props} />;
}

export function DrawerPortal(props: DrawerPrimitive.Portal.Props) {
  return <DrawerPrimitive.Portal data-slot="drawer-portal" {...props} />;
}

export function DrawerOverlay({
  className,
  ...props
}: DrawerPrimitive.Backdrop.Props) {
  return (
    <DrawerPrimitive.Backdrop
      data-slot="drawer-overlay"
      className={cn(
        "fixed inset-0 z-[90] min-h-dvh bg-black/70 opacity-[calc(1-var(--drawer-swipe-progress))] backdrop-blur-sm transition-opacity duration-300 data-starting-style:opacity-0 data-ending-style:opacity-0",
        className,
      )}
      {...props}
    />
  );
}

export function DrawerContent({
  className,
  children,
  ...props
}: DrawerPrimitive.Popup.Props) {
  return (
    <DrawerPortal>
      <DrawerOverlay />
      <DrawerPrimitive.Viewport className="pointer-events-none fixed inset-0 z-[100] flex items-stretch justify-end">
        <DrawerPrimitive.Popup
          data-slot="drawer-content"
          className={cn(
            "group/drawer-popup pointer-events-auto h-full w-[min(86vw,24rem)] overflow-y-auto border-l border-border bg-popover p-6 text-popover-foreground shadow-2xl outline-none [transform:translateX(var(--drawer-swipe-movement-x))] transition-transform duration-300 ease-out data-starting-style:translate-x-full data-ending-style:translate-x-full data-swiping:select-none",
            className,
          )}
          {...props}
        >
          <DrawerPrimitive.Content>{children}</DrawerPrimitive.Content>
        </DrawerPrimitive.Popup>
      </DrawerPrimitive.Viewport>
    </DrawerPortal>
  );
}

export function DrawerHeader({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return <div className={cn("grid gap-2", className)} {...props} />;
}

export function DrawerTitle({
  className,
  ...props
}: DrawerPrimitive.Title.Props) {
  return (
    <DrawerPrimitive.Title
      className={cn("text-lg font-semibold", className)}
      {...props}
    />
  );
}

export function DrawerDescription({
  className,
  ...props
}: DrawerPrimitive.Description.Props) {
  return (
    <DrawerPrimitive.Description
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}
