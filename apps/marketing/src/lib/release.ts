export interface WindowsReleaseAsset {
  bytes: number;
  href: string;
  label: { id: string; en: string };
  summary: { id: string; en: string };
}

export interface WindowsRelease {
  version: string;
  signed: boolean;
  releaseUrl: string;
  checksumsUrl: string;
  installer: WindowsReleaseAsset;
  portable: WindowsReleaseAsset;
}

const releaseBase =
  "https://github.com/myudak/hawkeye-judolgraph/releases/download/v1.0.0";

export const windowsRelease: WindowsRelease = {
  version: "1.0.0",
  signed: false,
  releaseUrl:
    "https://github.com/myudak/hawkeye-judolgraph/releases/tag/v1.0.0",
  checksumsUrl: `${releaseBase}/SHA256SUMS-windows.txt`,
  installer: {
    bytes: 220_713_976,
    href: `${releaseBase}/HAWK-EYE-Setup-1.0.0-windows-x64.exe`,
    label: { id: "Installer Windows", en: "Windows installer" },
    summary: {
      id: "Memasang aplikasi per pengguna, menu Start, dan uninstaller.",
      en: "Installs the per-user app, Start menu entry, and uninstaller.",
    },
  },
  portable: {
    bytes: 308_567_811,
    href: `${releaseBase}/HAWK-EYE-1.0.0-windows-x64-portable.zip`,
    label: { id: "Portable ZIP", en: "Portable ZIP" },
    summary: {
      id: "Ekstrak seluruh ZIP. Jangan pisahkan aplikasi dari folder _internal.",
      en: "Extract the complete ZIP. Keep the app beside its _internal folder.",
    },
  },
};

export function formatMegabytes(bytes: number): string {
  return `${Math.round(bytes / 1_000_000)} MB`;
}
