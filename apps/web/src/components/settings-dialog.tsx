import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowClockwise,
  Brain,
  CheckCircle,
  Eye,
  EyeSlash,
  GearSix,
  Key,
  PlugsConnected,
  ShieldCheck,
  Trash,
  WarningCircle,
} from "@phosphor-icons/react"
import { toast } from "sonner"

import { api } from "@/api/client"
import type { DesktopSettings, DesktopSettingsUpdate } from "@/api/types"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type Language = "en" | "id"

const copy = {
  en: {
    trigger: "Model settings",
    title: "Model provider",
    description:
      "Configure optional model assistance for new investigations. Deterministic fallback stays available.",
    localOnly: "Local credential boundary",
    localDetail:
      "The key is stored in your Windows user profile and is never returned to this interface.",
    unavailable: "Desktop settings are available in the packaged Windows app.",
    unavailableDetail:
      "For manual or Docker runs, configure HAWKEYE_LLM_* in the root .env file.",
    loadError: "Local settings could not be read",
    retry: "Try again",
    enabled: "Use model assistance",
    endpoint: "API base URL",
    model: "Model identifier",
    style: "API style",
    timeout: "Timeout (seconds)",
    key: "API key",
    keyStored: "A key is already stored. Leave blank to keep it.",
    keyEmpty:
      "Optional when your local endpoint does not require authentication.",
    reveal: "Show API key",
    conceal: "Hide API key",
    clear: "Remove stored key",
    cancelClear: "Keep stored key",
    save: "Save provider",
    saving: "Saving…",
    saved: "Model settings saved for new investigations",
    disabled:
      "Model assistance disabled; deterministic fallback remains active",
    configured: "Configured · not verified",
    configuredDetail:
      "No paid request is made here. The next investigation uses this provider.",
    fallback: "Deterministic fallback active",
    fallbackDetail: "No model provider is enabled for new investigations.",
    ready: "Model provider ready",
    unavailableState: "Provider unavailable",
    invalidState: "Configuration invalid",
  },
  id: {
    trigger: "Pengaturan model",
    title: "Penyedia model",
    description:
      "Atur bantuan model opsional untuk investigasi baru. Fallback deterministik tetap tersedia.",
    localOnly: "Batas kredensial lokal",
    localDetail:
      "Key disimpan di profil pengguna Windows dan tidak pernah dikirim kembali ke tampilan ini.",
    unavailable: "Pengaturan ini tersedia di aplikasi Windows HAWK-EYE.",
    unavailableDetail:
      "Untuk mode manual atau Docker, atur HAWKEYE_LLM_* di file .env root.",
    loadError: "Pengaturan lokal tidak dapat dibaca",
    retry: "Coba lagi",
    enabled: "Gunakan bantuan model",
    endpoint: "Base URL API",
    model: "ID model",
    style: "Gaya API",
    timeout: "Batas waktu (detik)",
    key: "API key",
    keyStored: "Key sudah tersimpan. Kosongkan kolom untuk mempertahankannya.",
    keyEmpty: "Opsional bila endpoint lokal tidak memerlukan autentikasi.",
    reveal: "Tampilkan API key",
    conceal: "Sembunyikan API key",
    clear: "Hapus key tersimpan",
    cancelClear: "Pertahankan key",
    save: "Simpan penyedia",
    saving: "Menyimpan…",
    saved: "Pengaturan model tersimpan untuk investigasi baru",
    disabled: "Bantuan model dimatikan; fallback deterministik tetap aktif",
    configured: "Terkonfigurasi · belum diverifikasi",
    configuredDetail:
      "Tidak ada request berbayar di sini. Investigasi berikutnya memakai penyedia ini.",
    fallback: "Fallback deterministik aktif",
    fallbackDetail:
      "Tidak ada penyedia model yang aktif untuk investigasi baru.",
    ready: "Penyedia model siap",
    unavailableState: "Penyedia tidak tersedia",
    invalidState: "Konfigurasi tidak valid",
  },
} as const

const emptyForm: DesktopSettingsUpdate = {
  enabled: false,
  base_url: "https://openrouter.ai/api/v1",
  model: "",
  api_style: "chat_completions",
  timeout_seconds: 30,
  api_key: "",
  clear_api_key: false,
}

function formFromSettings(settings?: DesktopSettings): DesktopSettingsUpdate {
  if (!settings?.available) return emptyForm
  return {
    enabled: settings.enabled,
    base_url: settings.base_url || "https://openrouter.ai/api/v1",
    model: settings.model || "",
    api_style: settings.api_style || "chat_completions",
    timeout_seconds: settings.timeout_seconds || 30,
    api_key: "",
    clear_api_key: false,
  }
}

export function SettingsDialog({ language }: { language: Language }) {
  const text = copy[language]
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [draft, setDraft] = useState<DesktopSettingsUpdate | null>(null)
  const settings = useQuery({
    queryKey: ["desktop-settings"],
    queryFn: api.settings,
    enabled: open,
    staleTime: 5_000,
    retry: false,
  })

  const form = draft ?? formFromSettings(settings.data)
  const updateForm = (
    update: (current: DesktopSettingsUpdate) => DesktopSettingsUpdate
  ) => setDraft((current) => update(current ?? formFromSettings(settings.data)))

  const save = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: (result) => {
      queryClient.setQueryData(["desktop-settings"], result)
      queryClient.invalidateQueries({ queryKey: ["capability"] })
      setDraft((current) => ({
        ...(current ?? formFromSettings(result)),
        api_key: "",
        clear_api_key: false,
      }))
      toast.success(result.enabled ? text.saved : text.disabled)
    },
    onError: (error) => toast.error(error.message),
  })

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    save.mutate(form)
  }

  const keyConfigured = Boolean(settings.data?.api_key_configured)
  const capability = settings.data?.capability
  const capabilityState = capability?.state ?? "fallback_only"
  const capabilityTitle =
    capabilityState === "model_ready"
      ? text.ready
      : capabilityState === "model_configured_unverified"
        ? text.configured
        : capabilityState === "model_unavailable"
          ? text.unavailableState
          : capabilityState === "configuration_invalid"
            ? text.invalidState
            : text.fallback
  const capabilityDetail =
    capabilityState === "model_configured_unverified" ||
    capabilityState === "model_ready"
      ? capability?.selected_model || text.configuredDetail
      : capabilityState === "fallback_only"
        ? text.fallbackDetail
        : text.configuredDetail

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (nextOpen) {
      setDraft(null)
      setShowKey(false)
      save.reset()
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger
        render={
          <Button
            className="header-settings"
            type="button"
            size="icon"
            variant="outline"
            aria-label={text.trigger}
          />
        }
      >
        <GearSix weight="bold" />
      </DialogTrigger>
      <DialogContent className="settings-dialog">
        <DialogHeader className="settings-heading">
          <span className="settings-heading-icon">
            <Brain weight="duotone" />
          </span>
          <span>
            <DialogTitle>{text.title}</DialogTitle>
            <DialogDescription>{text.description}</DialogDescription>
          </span>
        </DialogHeader>

        {settings.isPending ? (
          <div className="settings-loading" aria-live="polite">
            <span />
            <b>
              {language === "id"
                ? "Membaca konfigurasi lokal…"
                : "Reading local configuration…"}
            </b>
          </div>
        ) : settings.isError ? (
          <div
            className="settings-unavailable settings-load-error"
            role="alert"
          >
            <WarningCircle weight="duotone" />
            <span>
              <b>{text.loadError}</b>
              <small>{settings.error.message}</small>
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => settings.refetch()}
            >
              <ArrowClockwise />
              {text.retry}
            </Button>
          </div>
        ) : !settings.data?.available ? (
          <div className="settings-unavailable">
            <ShieldCheck weight="duotone" />
            <span>
              <b>{text.unavailable}</b>
              <small>{text.unavailableDetail}</small>
            </span>
          </div>
        ) : (
          <form className="settings-form" onSubmit={submit}>
            <div className="settings-privacy-note">
              <Key weight="duotone" />
              <span>
                <b>{text.localOnly}</b>
                <small>{text.localDetail}</small>
              </span>
              <CheckCircle weight="fill" />
            </div>

            <div
              className="settings-provider-state"
              data-state={capabilityState}
            >
              <span aria-hidden="true" />
              <div>
                <b>{capabilityTitle}</b>
                <small>{capabilityDetail}</small>
              </div>
              <em>
                {language === "id"
                  ? "Berlaku untuk investigasi baru"
                  : "Applies to new investigations"}
              </em>
            </div>

            <button
              type="button"
              className="settings-enable"
              aria-pressed={form.enabled}
              onClick={() =>
                updateForm((current) => ({
                  ...current,
                  enabled: !current.enabled,
                }))
              }
            >
              <span className="settings-switch" data-on={form.enabled}>
                <i />
              </span>
              <span>
                <b>{text.enabled}</b>
                <small>
                  {form.enabled
                    ? language === "id"
                      ? "Model digunakan hanya untuk memilih aksi aman yang diterbitkan server."
                      : "The model may only select safe actions issued by the server."
                    : language === "id"
                      ? "Investigasi tetap berjalan dengan fallback deterministik."
                      : "Investigations continue with deterministic fallback."}
                </small>
              </span>
            </button>

            <fieldset disabled={!form.enabled || save.isPending}>
              <div className="settings-grid">
                <div className="settings-field settings-field-wide">
                  <Label htmlFor="llm-base-url">{text.endpoint}</Label>
                  <span className="settings-input-shell">
                    <PlugsConnected weight="duotone" />
                    <Input
                      id="llm-base-url"
                      type="url"
                      required={form.enabled}
                      value={form.base_url}
                      onChange={(event) =>
                        updateForm((current) => ({
                          ...current,
                          base_url: event.target.value,
                        }))
                      }
                    />
                  </span>
                </div>

                <div className="settings-field settings-field-wide">
                  <Label htmlFor="llm-model">{text.model}</Label>
                  <Input
                    id="llm-model"
                    required={form.enabled}
                    value={form.model}
                    placeholder="openai/gpt-5.6-luna"
                    onChange={(event) =>
                      updateForm((current) => ({
                        ...current,
                        model: event.target.value,
                      }))
                    }
                  />
                </div>

                <div className="settings-field">
                  <Label htmlFor="llm-api-style">{text.style}</Label>
                  <Select
                    value={form.api_style}
                    onValueChange={(value) =>
                      updateForm((current) => ({
                        ...current,
                        api_style: value as DesktopSettingsUpdate["api_style"],
                      }))
                    }
                  >
                    <SelectTrigger
                      id="llm-api-style"
                      className="settings-select"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto</SelectItem>
                      <SelectItem value="responses">Responses</SelectItem>
                      <SelectItem value="chat_completions">
                        Chat Completions
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="settings-field">
                  <Label htmlFor="llm-timeout">{text.timeout}</Label>
                  <Input
                    id="llm-timeout"
                    type="number"
                    min={1}
                    max={60}
                    value={form.timeout_seconds}
                    onChange={(event) =>
                      updateForm((current) => ({
                        ...current,
                        timeout_seconds: Number(event.target.value),
                      }))
                    }
                  />
                </div>

                <div className="settings-field settings-field-wide">
                  <Label htmlFor="llm-api-key">{text.key}</Label>
                  <span className="settings-key-shell">
                    <Input
                      id="llm-api-key"
                      type={showKey ? "text" : "password"}
                      value={form.api_key || ""}
                      autoComplete="off"
                      placeholder={keyConfigured ? "••••••••••••••••" : "sk-…"}
                      onChange={(event) =>
                        updateForm((current) => ({
                          ...current,
                          api_key: event.target.value,
                          clear_api_key: false,
                        }))
                      }
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey((current) => !current)}
                      aria-label={showKey ? text.conceal : text.reveal}
                    >
                      {showKey ? <EyeSlash /> : <Eye />}
                    </button>
                  </span>
                  <small>
                    {keyConfigured ? text.keyStored : text.keyEmpty}
                  </small>
                </div>
              </div>

              {keyConfigured ? (
                <button
                  type="button"
                  className="settings-clear-key"
                  data-active={form.clear_api_key}
                  aria-pressed={form.clear_api_key}
                  onClick={() =>
                    updateForm((current) => ({
                      ...current,
                      api_key: "",
                      clear_api_key: !current.clear_api_key,
                    }))
                  }
                >
                  <Trash />
                  {form.clear_api_key ? text.cancelClear : text.clear}
                </button>
              ) : null}
            </fieldset>

            <DialogFooter className="settings-footer">
              <span>
                {language === "id"
                  ? "Tidak ada probe berbayar saat menyimpan."
                  : "Saving never performs a paid provider probe."}
              </span>
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? text.saving : text.save}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
