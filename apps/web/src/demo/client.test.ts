import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const session = new Map<string, string>()

beforeEach(() => {
  vi.resetModules()
  vi.stubEnv("MODE", "demo")
  vi.stubGlobal("sessionStorage", {
    getItem: (key: string) => session.get(key) ?? null,
    setItem: (key: string, value: string) => session.set(key, value),
  })
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      throw new Error("Unexpected network request")
    })
  )
  session.clear()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe("backend-free sample runtime", () => {
  it("plays a known scenario through completion, resumes after reload, and rejects arbitrary URLs", async () => {
    vi.useFakeTimers()
    const { api, jobPreviewUrl } = await import("@/demo/client")
    await expect(
      api.startJob({
        seed_url: "https://example.com",
        investigation_name: "",
        investigation_mode: "guided",
      })
    ).rejects.toThrow("supplied")
    const job = await api.startJob({
      seed_url: "https://harbor.demo.invalid/",
      investigation_name: "",
      investigation_mode: "guided",
    })
    expect(job.status).toBe("running")
    vi.advanceTimersByTime(2500)
    vi.resetModules()
    const reloaded = await import("@/demo/client")
    expect((await reloaded.api.activeJob()).job?.job_id).toBe(job.job_id)
    expect((await reloaded.api.getJob(job.job_id)).stage).toBe(
      "preserving_artifacts"
    )
    expect(jobPreviewUrl(job.job_id, 1)).not.toContain("/api/")
    vi.advanceTimersByTime(4000)
    const result = await reloaded.api.getJob(job.job_id)
    expect(result.status).toBe("completed")
    expect(result.result?.source_case?.observations).toHaveLength(3)
    expect((await reloaded.api.activeJob()).job).toBeNull()
    expect(fetch).not.toHaveBeenCalled()
  })

  it("requires approval before review and preserves bounded review versions until reset", async () => {
    const { api, resetDemo } = await import("@/demo/client")
    const review = {
      assertion_id: "demo-public-link",
      outcome: "verified",
      reviewer_label: "Demo reviewer",
      reason: "The source page visibly links to Harbor.",
    }
    await expect(api.appendReview("demo-related", review)).rejects.toThrow(
      "valid sample assertion"
    )
    await api.approveCandidate("demo-related")
    const approved = await api.getRun("demo-related")
    expect(approved.current_assertion_status).toBe("needs_review")
    expect(
      approved.graph.edges.find(
        (item) => item.id === "assertion:demo-public-link"
      )?.appearance
    ).toBe("dashed")
    await api.appendReview("demo-related", review)
    await api.appendReview("demo-related", { ...review, outcome: "rejected" })
    vi.resetModules()
    const reloaded = await import("@/demo/client")
    const run = await reloaded.api.getRun("demo-related")
    expect(run.reviews?.map((item) => item.new_version)).toEqual([1, 2])
    expect(run.current_assertion_status).toBe("rejected")
    expect(
      run.graph.edges.find((item) => item.id === "assertion:demo-public-link")
        ?.appearance
    ).toBe("rejected")
    reloaded.resetDemo()
    expect((await reloaded.api.getRun("demo-related")).lead_status).toBe(
      "waiting_for_approval"
    )
    resetDemo()
    expect(fetch).not.toHaveBeenCalled()
  })

  it("keeps restricted captures empty and uses only bundled artifacts", async () => {
    const { api, caseArtifactUrl, runArtifactUrl, runExportUrl } =
      await import("@/demo/client")
    const run = await api.getRun("demo-restricted")
    expect(run.capture_adequacy).toBe("limited")
    expect(run.source_case?.observations).toEqual([])
    expect(run.gambling_indicators?.indicator_count).toBe(0)
    const source = run.source_case!
    expect(
      caseArtifactUrl(source.case_id, source.evidence[0].id)
    ).not.toContain("/api/")
    expect(
      runArtifactUrl(run.workspace_id, run.artifacts[0].name)
    ).not.toContain("/api/")
    expect(() => caseArtifactUrl(source.case_id, "unknown")).toThrow(
      "Unknown sample artifact"
    )
    expect(() => runExportUrl(run.workspace_id, "zip")).toThrow(
      "Markdown and JSON"
    )
    expect(fetch).not.toHaveBeenCalled()
  })

  it("works with corrupt or unavailable browser storage", async () => {
    session.set("hawk-eye-demo-v1", "not json")
    const { api, resetDemo } = await import("@/demo/client")
    expect((await api.listRuns()).runs).toHaveLength(3)
    vi.stubGlobal("sessionStorage", {
      getItem: () => {
        throw new Error("Storage disabled")
      },
      setItem: () => {
        throw new Error("Storage disabled")
      },
    })
    resetDemo()
    await api.approveCandidate("demo-related")
    expect((await api.getRun("demo-related")).assertion?.assertion_type).toBe(
      "publicly_links_to"
    )
  })
})
