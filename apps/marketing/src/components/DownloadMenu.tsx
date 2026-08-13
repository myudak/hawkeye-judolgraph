import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLinkItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@hawkeye/ui";
import {
  CaretDownIcon,
  CheckCircleIcon,
  DownloadSimpleIcon,
  FileArchiveIcon,
  FileTextIcon,
  ShieldWarningIcon,
  WindowsLogoIcon,
} from "@phosphor-icons/react";
import { formatMegabytes, type WindowsRelease } from "../lib/release";
import { localize, useMarketingLanguage } from "../lib/language";

export function DownloadMenu({
  release,
  compact = false,
}: {
  release: WindowsRelease;
  compact?: boolean;
}) {
  const language = useMarketingLanguage();
  return (
    <div className="inline-flex max-w-full items-stretch rounded-full shadow-[0_14px_36px_rgb(237_23_100/0.18)]">
      <Button
        variant="outline"
        size={compact ? "default" : "lg"}
        className="h-auto min-h-11 rounded-r-none rounded-l-full bg-card/70 px-4"
        render={
          <a href={release.installer.href} target="_blank" rel="noreferrer" />
        }
      >
        <DownloadSimpleIcon data-icon="inline-start" />
        <span>
          {localize(language, {
            id: compact ? "Unduh" : "Unduh installer",
            en: compact ? "Download" : "Download installer",
          })}
        </span>
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="grid min-h-11 w-11 place-items-center rounded-r-full border border-l-0 border-border bg-card/70 text-foreground outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/30"
          aria-label={localize(language, {
            id: "Pilih paket Windows",
            en: "Choose a Windows package",
          })}
        >
          <CaretDownIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <div className="px-3 py-2">
            <p className="m-0 text-sm font-semibold">
              HAWK-EYE v{release.version}
            </p>
            <p className="mt-1 mb-0 text-xs text-muted-foreground">
              {localize(language, {
                id: "Pilih cara menjalankan HAWK-EYE di Windows.",
                en: "Choose how to run HAWK-EYE on Windows.",
              })}
            </p>
          </div>
          <DropdownMenuLinkItem
            href={release.installer.href}
            target="_blank"
            rel="noreferrer"
          >
            <WindowsLogoIcon
              className="mt-0.5 size-5 shrink-0 text-primary"
              weight="fill"
            />
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2 font-semibold">
                {localize(language, release.installer.label)}
                <span className="rounded-full bg-primary/12 px-2 py-0.5 text-[0.65rem] text-primary">
                  {localize(language, {
                    id: "Direkomendasikan",
                    en: "Recommended",
                  })}
                </span>
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                {localize(language, release.installer.summary)}
              </span>
            </span>
            <span className="text-xs tabular-nums text-muted-foreground">
              {formatMegabytes(release.installer.bytes)}
            </span>
          </DropdownMenuLinkItem>
          <DropdownMenuLinkItem
            href={release.portable.href}
            target="_blank"
            rel="noreferrer"
          >
            <FileArchiveIcon className="mt-0.5 size-5 shrink-0 text-teal-400" />
            <span className="min-w-0 flex-1">
              <span className="font-semibold">
                {localize(language, release.portable.label)}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                {localize(language, release.portable.summary)}
              </span>
            </span>
            <span className="text-xs tabular-nums text-muted-foreground">
              {formatMegabytes(release.portable.bytes)}
            </span>
          </DropdownMenuLinkItem>
          <DropdownMenuSeparator />
          <div className="mx-2 my-2 flex gap-2 rounded-xl border border-amber-400/20 bg-amber-400/8 p-3 text-xs leading-relaxed text-muted-foreground">
            <ShieldWarningIcon className="mt-0.5 size-4 shrink-0 text-amber-400" />
            <span>
              {localize(language, {
                id: "Build ini belum ditandatangani dengan sertifikat code-signing. Windows dapat menampilkan peringatan SmartScreen. Periksa SHA-256 sebelum menjalankan.",
                en: "This build is not code-signed. Windows may show a SmartScreen warning. Verify its SHA-256 before running it.",
              })}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1">
            <DropdownMenuLinkItem
              className="items-center py-2"
              href={release.checksumsUrl}
              target="_blank"
              rel="noreferrer"
            >
              <CheckCircleIcon className="size-4 text-teal-400" />
              <span className="text-xs font-medium">SHA-256</span>
            </DropdownMenuLinkItem>
            <DropdownMenuLinkItem
              className="items-center py-2"
              href={release.releaseUrl}
              target="_blank"
              rel="noreferrer"
            >
              <FileTextIcon className="size-4 text-primary" />
              <span className="text-xs font-medium">
                {localize(language, {
                  id: "Catatan rilis",
                  en: "Release notes",
                })}
              </span>
            </DropdownMenuLinkItem>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
