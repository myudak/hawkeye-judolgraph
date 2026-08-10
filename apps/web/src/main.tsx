import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router-dom"
import { Toaster } from "sonner"

import App from "@/App"
import { TooltipProvider } from "@/components/ui/tooltip"
import "@/index.css"

document.documentElement.classList.add("dark")

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <HashRouter>
          <App />
        </HashRouter>
        <Toaster theme="dark" richColors position="bottom-right" />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>
)
