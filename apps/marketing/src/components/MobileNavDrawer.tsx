import { Logo } from "@hawkeye/brand";
import {
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

export function MobileNavDrawer({
  avatar,
  demoUrl,
  repositoryUrl,
  releaseUrl,
}: {
  avatar: string;
  demoUrl: string;
  repositoryUrl: string;
  releaseUrl: string;
}) {
  const navigation = [
    { id: "Platform", en: "Platform", href: "#platform" },
    { id: "Cara kerja", en: "How it works", href: "#how-it-works" },
    { id: "Keamanan", en: "Safety", href: "#safety" },
    { id: "Perbandingan", en: "Compare", href: "#compare" },
  ];

  return (
    <Drawer swipeDirection="right">
      <DrawerTrigger className="mobile-menu-button" aria-label="Buka navigasi">
        <ListIcon aria-hidden="true" weight="bold" />
      </DrawerTrigger>
      <DrawerContent className="mobile-drawer">
        <DrawerHeader className="mobile-drawer__header">
          <Logo compact imageSrc={avatar} />
          <div>
            <DrawerTitle>Menu</DrawerTitle>
            <DrawerDescription>Jelajahi HAWK-EYE</DrawerDescription>
          </div>
          <DrawerClose
            className="mobile-drawer__close"
            aria-label="Tutup navigasi"
          >
            <XIcon aria-hidden="true" />
          </DrawerClose>
        </DrawerHeader>
        <nav className="mobile-drawer__nav" aria-label="Navigasi seluler">
          {navigation.map((item, index) => (
            <DrawerClose key={item.href} render={<a href={item.href} />}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span className="lang-id">{item.id}</span>
              <span className="lang-en">{item.en}</span>
              <ArrowUpRightIcon aria-hidden="true" />
            </DrawerClose>
          ))}
        </nav>
        <div className="mobile-drawer__actions">
          <DrawerClose
            render={<a href={demoUrl} target="_blank" rel="noreferrer" />}
          >
            <span className="lang-id">Coba demo online</span>
            <span className="lang-en">Try online demo</span>
            <ArrowUpRightIcon aria-hidden="true" />
          </DrawerClose>
          <DrawerClose
            render={<a href={releaseUrl} target="_blank" rel="noreferrer" />}
          >
            <DownloadSimpleIcon aria-hidden="true" />
            <span className="lang-id">Unduh untuk Windows</span>
            <span className="lang-en">Download for Windows</span>
          </DrawerClose>
          <a href={repositoryUrl} target="_blank" rel="noreferrer">
            <span className="lang-id">Lihat kode di GitHub</span>
            <span className="lang-en">View source on GitHub</span>
            <ArrowUpRightIcon aria-hidden="true" />
          </a>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
