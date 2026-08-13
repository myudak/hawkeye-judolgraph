import { Logo } from "@hawkeye/brand";
import {
  Button,
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@hawkeye/ui";
import {
  ArrowUpRightIcon,
  DownloadSimpleIcon,
  ListIcon,
  XIcon,
} from "@phosphor-icons/react";
import type { WindowsRelease } from "../lib/release";

export function MobileNavDrawer({
  avatar,
  demoUrl,
  repositoryUrl,
  release,
}: {
  avatar: string;
  demoUrl: string;
  repositoryUrl: string;
  release: WindowsRelease;
}) {
  const navigation = [
    { id: "Produk", en: "Product", href: "#platform" },
    { id: "Cara kerja", en: "How it works", href: "#how-it-works" },
    { id: "Teknologi", en: "Technology", href: "#technology" },
    { id: "Evaluasi", en: "Evaluation", href: "#evaluation" },
    { id: "Batas pengumpulan", en: "Collection limits", href: "#safety" },
  ];

  return (
    <Drawer swipeDirection="right">
      <DrawerTrigger
        className="inline-flex size-10 items-center justify-center rounded-lg border border-border bg-card text-foreground transition-colors hover:bg-accent lg:hidden"
        aria-label="Buka navigasi"
      >
        <ListIcon aria-hidden="true" weight="bold" className="size-5" />
      </DrawerTrigger>
      <DrawerContent className="flex flex-col gap-7 bg-[var(--hk-panel)]">
        <DrawerHeader className="grid grid-cols-[1fr_auto] items-start gap-4 border-b border-border pb-5">
          <div className="flex items-center gap-3">
            <Logo compact imageSrc={avatar} />
            <div>
              <DrawerTitle>HAWK-EYE</DrawerTitle>
              <DrawerDescription>
                <span className="lang-id">Navigasi produk</span>
                <span className="lang-en">Product navigation</span>
              </DrawerDescription>
            </div>
          </div>
          <DrawerClose
            className="inline-flex size-9 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Tutup navigasi"
          >
            <XIcon aria-hidden="true" />
          </DrawerClose>
        </DrawerHeader>

        <nav className="grid" aria-label="Navigasi seluler">
          {navigation.map((item, index) => (
            <DrawerClose
              key={item.href}
              className="grid grid-cols-[2.5rem_1fr_auto] items-center gap-3 border-b border-border py-4 text-left text-sm font-medium hover:text-[var(--hk-pink)]"
              render={<a href={item.href} />}
            >
              <span className="font-mono text-xs text-muted-foreground">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="lang-id">{item.id}</span>
              <span className="lang-en">{item.en}</span>
              <ArrowUpRightIcon aria-hidden="true" />
            </DrawerClose>
          ))}
        </nav>

        <div className="mt-auto grid gap-3">
          <DrawerClose
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-[var(--hk-pink)] px-4 text-sm font-semibold text-white hover:brightness-110"
            render={<a href={demoUrl} target="_blank" rel="noreferrer" />}
          >
            <span className="lang-id">Buka HAWK-EYE di browser</span>
            <span className="lang-en">Open HAWK-EYE in your browser</span>
            <ArrowUpRightIcon aria-hidden="true" />
          </DrawerClose>
          <Button
            variant="outline"
            render={
              <a href={release.installer.href}>
                <DownloadSimpleIcon aria-hidden="true" />
                <span className="lang-id">Unduh installer</span>
                <span className="lang-en">Download installer</span>
                <span className="text-xs text-muted-foreground">
                  {Math.round(release.installer.bytes / 1_000_000)} MB
                </span>
              </a>
            }
          />
          <Button
            variant="ghost"
            render={
              <a href={release.portable.href}>
                <span className="lang-id">Portable ZIP</span>
                <span className="lang-en">Portable ZIP</span>
                <span className="text-xs text-muted-foreground">
                  {Math.round(release.portable.bytes / 1_000_000)} MB
                </span>
              </a>
            }
          />
          <a
            className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground hover:text-foreground"
            href={repositoryUrl}
            target="_blank"
            rel="noreferrer"
          >
            <span className="lang-id">Kode sumber di GitHub</span>
            <span className="lang-en">Source code on GitHub</span>
            <ArrowUpRightIcon aria-hidden="true" />
          </a>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
