import { Desktop, Moon, Sun } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useTheme } from "@/components/theme-provider"

export function ThemeMenu({ language }: { language: "en" | "id" }) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const Icon = resolvedTheme === "dark" ? Moon : Sun
  const label = language === "id" ? "Tema tampilan" : "Display theme"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={label}
            title={label}
          >
            <Icon weight="bold" />
          </Button>
        }
      />
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{label}</DropdownMenuLabel>
          <DropdownMenuItem onClick={() => setTheme("light")}>
            <Sun /> {language === "id" ? "Terang" : "Light"}
            {theme === "light" ? <span className="ml-auto">✓</span> : null}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTheme("dark")}>
            <Moon /> {language === "id" ? "Gelap" : "Dark"}
            {theme === "dark" ? <span className="ml-auto">✓</span> : null}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTheme("system")}>
            <Desktop /> {language === "id" ? "Ikuti sistem" : "System"}
            {theme === "system" ? <span className="ml-auto">✓</span> : null}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
