import {
  CornersOut,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
} from "@phosphor-icons/react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { drawOfficialSocialIcon } from "@hawkeye/graph/canvas-icons"
import { graphMotion } from "@hawkeye/graph/theme"
import {
  applyMagneticForces,
  releaseWithMomentum,
} from "@hawkeye/graph/force-simulation"

import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type {
  GraphEdge,
  GraphIconKind,
  GraphLens,
  GraphNode,
  GraphProjection,
  VisualKind,
} from "@/lib/graph"
import {
  GRAPH_LENSES,
  graphLensAllows,
  graphNodeText,
  graphOrbitTarget,
  seededUnit,
} from "@/lib/graph"
import { truncate } from "@/lib/format"

interface SimNode extends GraphNode {
  x: number
  y: number
  vx: number
  vy: number
  tx: number
  ty: number
  pinned: boolean
  bornAt: number
}

interface Camera {
  x: number
  y: number
  zoom: number
  targetX: number
  targetY: number
  targetZoom: number
}

interface PointerState {
  id: number
  startX: number
  startY: number
  cameraX: number
  cameraY: number
  dragId?: string
  moved: boolean
}

interface ScreenPoint {
  x: number
  y: number
}

function rgba(hex: string, alpha: number): string {
  const clean = hex.replace("#", "")
  const value = Number.parseInt(clean, 16)
  const red = (value >> 16) & 255
  const green = (value >> 8) & 255
  const blue = value & 255
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}

function circle(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number
) {
  context.beginPath()
  context.arc(x, y, radius, 0, Math.PI * 2)
}

function boundedForFit(value: number, target: number): number {
  return Math.max(target - 110, Math.min(target + 110, value))
}

function drawGraphIcon(
  context: CanvasRenderingContext2D,
  kind: GraphIconKind,
  x: number,
  y: number,
  size: number,
  color: string
) {
  const s = size
  if (kind === "telegram" || kind === "whatsapp") {
    drawOfficialSocialIcon(context, kind, x, y, s * 2)
    return
  }
  context.save()
  context.translate(x, y)
  context.strokeStyle = color
  context.fillStyle = "transparent"
  context.lineWidth = Math.max(1.25, s * 0.11)
  context.lineCap = "round"
  context.lineJoin = "round"
  context.beginPath()

  if (kind === "site") {
    context.arc(0, 0, s * 0.67, 0, Math.PI * 2)
    context.moveTo(-s * 0.65, 0)
    context.lineTo(s * 0.65, 0)
    context.moveTo(0, -s * 0.66)
    context.bezierCurveTo(
      -s * 0.36,
      -s * 0.35,
      -s * 0.36,
      s * 0.35,
      0,
      s * 0.66
    )
    context.moveTo(0, -s * 0.66)
    context.bezierCurveTo(s * 0.36, -s * 0.35, s * 0.36, s * 0.35, 0, s * 0.66)
  } else if (kind === "page") {
    context.roundRect(-s * 0.53, -s * 0.67, s * 1.06, s * 1.34, s * 0.12)
    context.moveTo(-s * 0.33, -s * 0.28)
    context.lineTo(s * 0.31, -s * 0.28)
    context.moveTo(-s * 0.33, 0.03)
    context.lineTo(s * 0.2, 0.03)
    context.moveTo(-s * 0.33, s * 0.33)
    context.lineTo(s * 0.28, s * 0.33)
  } else if (kind === "email") {
    context.roundRect(-s * 0.7, -s * 0.48, s * 1.4, s * 0.96, s * 0.12)
    context.moveTo(-s * 0.64, -s * 0.38)
    context.lineTo(0, s * 0.08)
    context.lineTo(s * 0.64, -s * 0.38)
  } else if (kind === "phone") {
    context.moveTo(-s * 0.5, -s * 0.55)
    context.quadraticCurveTo(-s * 0.68, -s * 0.38, -s * 0.46, s * 0.04)
    context.quadraticCurveTo(-s * 0.09, s * 0.62, s * 0.43, s * 0.55)
    context.quadraticCurveTo(s * 0.66, s * 0.5, s * 0.5, s * 0.22)
    context.lineTo(s * 0.28, 0)
    context.quadraticCurveTo(s * 0.17, -s * 0.09, s * 0.03, s * 0.05)
    context.lineTo(-s * 0.08, s * 0.16)
    context.quadraticCurveTo(-s * 0.28, 0, -s * 0.31, -s * 0.17)
    context.lineTo(-s * 0.17, -s * 0.31)
    context.quadraticCurveTo(-s * 0.08, -s * 0.43, -s * 0.22, -s * 0.54)
    context.closePath()
  } else if (kind === "contact") {
    context.arc(0, -s * 0.29, s * 0.28, 0, Math.PI * 2)
    context.moveTo(-s * 0.58, s * 0.62)
    context.quadraticCurveTo(-s * 0.48, s * 0.12, 0, s * 0.12)
    context.quadraticCurveTo(s * 0.48, s * 0.12, s * 0.58, s * 0.62)
  } else if (kind === "brand") {
    context.moveTo(-s * 0.62, -s * 0.54)
    context.lineTo(s * 0.14, -s * 0.54)
    context.lineTo(s * 0.66, -s * 0.02)
    context.lineTo(s * 0.02, s * 0.62)
    context.lineTo(-s * 0.62, -s * 0.02)
    context.closePath()
    context.moveTo(-s * 0.29, -s * 0.24)
    context.arc(-s * 0.29, -s * 0.24, s * 0.09, 0, Math.PI * 2)
  } else if (kind === "payment") {
    context.roundRect(-s * 0.7, -s * 0.5, s * 1.4, s, s * 0.16)
    context.moveTo(-s * 0.65, -s * 0.18)
    context.lineTo(s * 0.65, -s * 0.18)
    context.moveTo(-s * 0.44, s * 0.2)
    context.lineTo(-s * 0.08, s * 0.2)
  } else if (kind === "offer") {
    context.arc(-s * 0.34, -s * 0.33, s * 0.15, 0, Math.PI * 2)
    context.moveTo(-s * 0.49, s * 0.5)
    context.lineTo(s * 0.49, -s * 0.5)
    context.moveTo(s * 0.34, s * 0.33)
    context.arc(s * 0.34, s * 0.33, s * 0.15, 0, Math.PI * 2)
  } else if (kind === "external") {
    context.roundRect(-s * 0.62, -s * 0.42, s * 1.04, s * 1.04, s * 0.12)
    context.moveTo(-s * 0.03, s * 0.03)
    context.lineTo(s * 0.62, -s * 0.62)
    context.moveTo(s * 0.14, -s * 0.62)
    context.lineTo(s * 0.62, -s * 0.62)
    context.lineTo(s * 0.62, -s * 0.14)
  } else if (kind === "candidate") {
    context.arc(-s * 0.08, -s * 0.08, s * 0.45, 0, Math.PI * 2)
    context.moveTo(s * 0.26, s * 0.26)
    context.lineTo(s * 0.67, s * 0.67)
    context.moveTo(-s * 0.08, -s * 0.28)
    context.lineTo(-s * 0.08, s * 0.02)
    context.moveTo(-s * 0.08, s * 0.2)
    context.lineTo(-s * 0.08, s * 0.21)
  } else {
    for (const offset of [-0.42, 0, 0.42]) {
      context.moveTo(offset * s + s * 0.09, 0)
      context.arc(offset * s, 0, s * 0.09, 0, Math.PI * 2)
    }
  }

  context.stroke()
  context.restore()
}

function createSimulation(nodes: GraphNode[]): Map<string, SimNode> {
  const buckets = new Map<VisualKind, GraphNode[]>()
  for (const node of nodes) {
    const kind = node.presentation.visualKind
    const items = buckets.get(kind) ?? []
    items.push(node)
    buckets.set(kind, items)
  }
  const simulation = new Map<string, SimNode>()
  const bornAt = performance.now()
  let order = 0
  for (const items of buckets.values()) {
    items.forEach((node, index) => {
      const target = graphOrbitTarget(node, index, items.length)
      simulation.set(node.id, {
        ...node,
        x: node.primary
          ? 0
          : target.x * 0.48 + (seededUnit(`${node.id}:x`) - 0.5) * 70,
        y: node.primary
          ? 0
          : target.y * 0.48 + (seededUnit(`${node.id}:y`) - 0.5) * 70,
        vx: 0,
        vy: 0,
        tx: target.x,
        ty: target.y,
        pinned: false,
        bornAt: node.primary ? bornAt : bornAt + order * 24,
      })
      order += 1
    })
  }
  return simulation
}

function curveControl(
  source: ScreenPoint,
  target: ScreenPoint,
  seed: number
): ScreenPoint {
  const dx = target.x - source.x
  const dy = target.y - source.y
  const length = Math.max(1, Math.hypot(dx, dy))
  const bend = (seed - 0.5) * Math.min(44, length * 0.18)
  return {
    x: (source.x + target.x) / 2 - (dy / length) * bend,
    y: (source.y + target.y) / 2 + (dx / length) * bend,
  }
}

function curvePoint(
  source: ScreenPoint,
  control: ScreenPoint,
  target: ScreenPoint,
  amount: number
): ScreenPoint {
  const inverse = 1 - amount
  return {
    x:
      inverse * inverse * source.x +
      2 * inverse * amount * control.x +
      amount * amount * target.x,
    y:
      inverse * inverse * source.y +
      2 * inverse * amount * control.y +
      amount * amount * target.y,
  }
}

function edgeColor(edge: GraphEdge, target?: SimNode): string {
  if (edge.appearance === "rejected" || edge.appearance === "hidden") {
    return "#ff6577"
  }
  if (edge.appearance === "dashed") return "#9a8cb8"
  return target?.presentation.color ?? "#718096"
}

export function EvidenceGraph({
  projection,
  selectedId,
  onSelect,
  filters,
  playbackCutoff,
  searchQuery,
  lens,
  onLensChange,
  language,
}: {
  projection: GraphProjection
  selectedId?: string | null
  onSelect: (node: GraphNode) => void
  filters: ReadonlySet<VisualKind>
  playbackCutoff: number
  searchQuery: string
  lens: GraphLens
  onLensChange: (lens: GraphLens) => void
  language: "en" | "id"
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const minimapRef = useRef<HTMLCanvasElement>(null)
  const simulationRef = useRef(createSimulation(projection.nodes))
  const cameraRef = useRef<Camera>({
    x: 0,
    y: 0,
    zoom: 0.78,
    targetX: 0,
    targetY: 0,
    targetZoom: 0.78,
  })
  const pointerRef = useRef<PointerState | null>(null)
  const hoveredIdRef = useRef<string | null>(null)
  const sizeRef = useRef({ width: 800, height: 600, dpr: 1 })
  const propsRef = useRef({
    filters,
    playbackCutoff,
    searchQuery,
    selectedId,
    projection,
    lens,
  })
  const [hovered, setHovered] = useState<{
    node: GraphNode
    x: number
    y: number
  } | null>(null)
  const reduceMotion = useMemo(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    []
  )

  useEffect(() => {
    propsRef.current = {
      filters,
      playbackCutoff,
      searchQuery,
      selectedId,
      projection,
      lens,
    }
  }, [filters, lens, playbackCutoff, projection, searchQuery, selectedId])

  const isVisible = useCallback((node: SimNode) => {
    const current = propsRef.current
    return (
      node.sequence <= current.playbackCutoff &&
      current.filters.has(node.presentation.visualKind) &&
      graphLensAllows(node, current.lens)
    )
  }, [])

  const worldToScreen = useCallback(
    (node: SimNode, time: number) => {
      const camera = cameraRef.current
      const size = sizeRef.current
      const float = reduceMotion
        ? 0
        : Math.sin(time * 0.00082 + seededUnit(node.id) * Math.PI * 2) * 1.5
      return {
        x: (node.x - camera.x) * camera.zoom + size.width / 2,
        y: (node.y + float - camera.y) * camera.zoom + size.height / 2,
      }
    },
    [reduceMotion]
  )

  const screenToWorld = useCallback((x: number, y: number) => {
    const camera = cameraRef.current
    const size = sizeRef.current
    return {
      x: (x - size.width / 2) / camera.zoom + camera.x,
      y: (y - size.height / 2) / camera.zoom + camera.y,
    }
  }, [])

  const fitGraph = useCallback(() => {
    const visible = [...simulationRef.current.values()].filter(isVisible)
    if (!visible.length) return
    const bounds = visible.reduce(
      (acc, node) => ({
        minX:
          Math.min(acc.minX, boundedForFit(node.x, node.tx), node.tx) -
          node.radius,
        maxX:
          Math.max(acc.maxX, boundedForFit(node.x, node.tx), node.tx) +
          node.radius,
        minY:
          Math.min(acc.minY, boundedForFit(node.y, node.ty), node.ty) -
          node.radius -
          28,
        maxY:
          Math.max(acc.maxY, boundedForFit(node.y, node.ty), node.ty) +
          node.radius +
          46,
      }),
      { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
    )
    const width = Math.max(220, bounds.maxX - bounds.minX + 150)
    const height = Math.max(180, bounds.maxY - bounds.minY + 270)
    const camera = cameraRef.current
    camera.targetZoom = Math.max(
      0.58,
      Math.min(
        1.35,
        Math.min(sizeRef.current.width / width, sizeRef.current.height / height)
      )
    )
    camera.targetX = (bounds.minX + bounds.maxX) / 2
    camera.targetY = (bounds.minY + bounds.maxY) / 2 - 72 / camera.targetZoom
  }, [isVisible])

  useEffect(() => {
    simulationRef.current = createSimulation(projection.nodes)
    cameraRef.current = {
      x: 0,
      y: 0,
      zoom: 0.78,
      targetX: 0,
      targetY: 0,
      targetZoom: 0.78,
    }
    const initialTimer = window.setTimeout(fitGraph, 90)
    const settledTimer = window.setTimeout(fitGraph, 950)
    const denseGraphTimer = window.setTimeout(fitGraph, 2600)
    return () => {
      window.clearTimeout(initialTimer)
      window.clearTimeout(settledTimer)
      window.clearTimeout(denseGraphTimer)
    }
  }, [fitGraph, projection])

  useEffect(() => {
    const timer = window.setTimeout(fitGraph, 60)
    return () => window.clearTimeout(timer)
  }, [filters, fitGraph, lens, playbackCutoff])

  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    const minimap = minimapRef.current
    if (!container || !canvas || !minimap) return
    const resize = () => {
      const bounds = container.getBoundingClientRect()
      const dpr = Math.min(1.75, window.devicePixelRatio || 1)
      const width = Math.max(320, bounds.width)
      const height = Math.max(430, bounds.height)
      sizeRef.current = { width, height, dpr }
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      const miniBounds = minimap.getBoundingClientRect()
      minimap.width = Math.floor(miniBounds.width * dpr)
      minimap.height = Math.floor(miniBounds.height * dpr)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    resize()
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    const minimap = minimapRef.current
    if (!canvas || !minimap) return
    const context = canvas.getContext("2d", { alpha: true })
    const mini = minimap.getContext("2d", { alpha: true })
    if (!context || !mini) return
    let frame = 0
    let last = performance.now()

    const visibleEdges = (nodes: SimNode[]) => {
      const ids = new Set(nodes.map((node) => node.id))
      return propsRef.current.projection.edges.filter(
        (edge) =>
          edge.sequence <= propsRef.current.playbackCutoff &&
          ids.has(edge.source) &&
          ids.has(edge.target)
      )
    }

    const physics = (delta: number) => {
      const nodes = [...simulationRef.current.values()].filter(isVisible)
      const edges = visibleEdges(nodes)
      applyMagneticForces({
        nodes,
        edges,
        time: performance.now(),
        delta,
        reducedMotion: reduceMotion,
        nodeById: (id) => simulationRef.current.get(id),
      })
    }

    const drawMinimap = (nodes: SimNode[], edges: GraphEdge[]) => {
      const dpr = sizeRef.current.dpr
      const width = minimap.width / dpr
      const height = minimap.height / dpr
      mini.setTransform(dpr, 0, 0, dpr, 0, 0)
      mini.clearRect(0, 0, width, height)
      mini.fillStyle = "rgba(4, 13, 23, 0.94)"
      mini.fillRect(0, 0, width, height)
      if (!nodes.length) return
      const bounds = nodes.reduce(
        (acc, node) => ({
          minX: Math.min(acc.minX, node.x),
          maxX: Math.max(acc.maxX, node.x),
          minY: Math.min(acc.minY, node.y),
          maxY: Math.max(acc.maxY, node.y),
        }),
        { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
      )
      const scale = Math.min(
        (width - 22) / Math.max(1, bounds.maxX - bounds.minX),
        (height - 18) / Math.max(1, bounds.maxY - bounds.minY)
      )
      const mapPoint = (node: SimNode) => ({
        x: 11 + (node.x - bounds.minX) * scale,
        y: 9 + (node.y - bounds.minY) * scale,
      })
      mini.lineWidth = 0.75
      mini.strokeStyle = "rgba(122, 145, 162, 0.24)"
      for (const edge of edges) {
        const source = simulationRef.current.get(edge.source)
        const target = simulationRef.current.get(edge.target)
        if (!source || !target) continue
        const a = mapPoint(source)
        const b = mapPoint(target)
        mini.beginPath()
        mini.moveTo(a.x, a.y)
        mini.lineTo(b.x, b.y)
        mini.stroke()
      }
      for (const node of nodes) {
        const point = mapPoint(node)
        mini.fillStyle = node.presentation.color
        mini.beginPath()
        mini.arc(point.x, point.y, node.primary ? 3.5 : 2.2, 0, Math.PI * 2)
        mini.fill()
      }
      const camera = cameraRef.current
      const worldWidth = sizeRef.current.width / camera.zoom
      const worldHeight = sizeRef.current.height / camera.zoom
      mini.strokeStyle = "rgba(222, 235, 245, 0.58)"
      mini.lineWidth = 0.8
      mini.strokeRect(
        11 + (camera.x - worldWidth / 2 - bounds.minX) * scale,
        9 + (camera.y - worldHeight / 2 - bounds.minY) * scale,
        worldWidth * scale,
        worldHeight * scale
      )
    }

    const drawOrbitGuides = (time: number) => {
      const root = [...simulationRef.current.values()].find(
        (node) => node.primary && isVisible(node)
      )
      if (!root) return
      const rootPoint = worldToScreen(root, time)
      const camera = cameraRef.current
      context.save()
      context.setLineDash([4, 8])
      context.lineWidth = 0.7
      for (const radius of [155, 225, 305]) {
        circle(context, rootPoint.x, rootPoint.y, radius * camera.zoom)
        context.strokeStyle = "rgba(100, 128, 149, 0.14)"
        context.stroke()
      }
      context.restore()
    }

    const drawEdgeLabel = (
      edge: GraphEdge,
      source: ScreenPoint,
      control: ScreenPoint,
      target: ScreenPoint,
      alpha: number
    ) => {
      const point = curvePoint(source, control, target, 0.5)
      const text = truncate(edge.relation.replaceAll("_", " "), 29)
      context.save()
      context.globalAlpha = alpha
      context.font = "600 9px 'Geist Variable', sans-serif"
      context.textAlign = "center"
      context.textBaseline = "middle"
      const width = context.measureText(text).width + 14
      context.fillStyle = "rgba(3, 11, 19, 0.92)"
      context.strokeStyle = "rgba(129, 155, 174, 0.28)"
      context.lineWidth = 0.75
      context.beginPath()
      context.roundRect(point.x - width / 2, point.y - 10, width, 20, 6)
      context.fill()
      context.stroke()
      context.fillStyle = "#bac7d1"
      context.fillText(text, point.x, point.y + 0.5)
      context.restore()
    }

    const paint = (time: number) => {
      const delta = Math.min(32, time - last)
      last = time
      physics(delta)
      const camera = cameraRef.current
      camera.x += (camera.targetX - camera.x) * graphMotion.cameraEase
      camera.y += (camera.targetY - camera.y) * graphMotion.cameraEase
      camera.zoom += (camera.targetZoom - camera.zoom) * graphMotion.cameraEase
      const { width, height, dpr } = sizeRef.current
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
      context.clearRect(0, 0, width, height)
      drawOrbitGuides(time)

      const nodes = [...simulationRef.current.values()].filter(isVisible)
      const edges = visibleEdges(nodes)
      const query = propsRef.current.searchQuery.trim().toLowerCase()
      const selectedNode = propsRef.current.selectedId
        ? simulationRef.current.get(propsRef.current.selectedId)
        : undefined
      const focusId =
        hoveredIdRef.current ||
        (selectedNode && !selectedNode.primary ? selectedNode.id : null)
      const focusSet = new Set<string>()
      if (focusId) {
        focusSet.add(focusId)
        for (const edge of edges) {
          if (edge.source === focusId) focusSet.add(edge.target)
          if (edge.target === focusId) focusSet.add(edge.source)
        }
      }

      for (const edge of edges) {
        const source = simulationRef.current.get(edge.source)
        const target = simulationRef.current.get(edge.target)
        if (!source || !target) continue
        const a = worldToScreen(source, time)
        const b = worldToScreen(target, time)
        const control = curveControl(a, b, edge.seed)
        const contextual =
          !focusId || edge.source === focusId || edge.target === focusId
        const sourceMatches =
          !query ||
          `${source.label} ${source.presentation.label}`
            .toLowerCase()
            .includes(query)
        const targetMatches =
          !query ||
          `${target.label} ${target.presentation.label}`
            .toLowerCase()
            .includes(query)
        const searchRelevant = !query || sourceMatches || targetMatches
        const alpha = contextual && searchRelevant ? 0.66 : 0.07
        const color = edgeColor(edge, target)
        context.save()
        context.globalAlpha = alpha
        context.beginPath()
        context.moveTo(a.x, a.y)
        context.quadraticCurveTo(control.x, control.y, b.x, b.y)
        context.strokeStyle = color
        context.lineWidth = contextual ? 1.35 : 0.8
        context.setLineDash(
          edge.appearance === "dashed" || edge.appearance === "rejected"
            ? [6, 6]
            : []
        )
        context.stroke()
        context.setLineDash([])

        if (contextual) {
          const arrow = curvePoint(a, control, b, 0.78)
          const before = curvePoint(a, control, b, 0.74)
          const angle = Math.atan2(arrow.y - before.y, arrow.x - before.x)
          context.translate(arrow.x, arrow.y)
          context.rotate(angle)
          context.fillStyle = color
          context.beginPath()
          context.moveTo(4.5, 0)
          context.lineTo(-3.5, -2.7)
          context.lineTo(-3.5, 2.7)
          context.closePath()
          context.fill()
          context.setTransform(dpr, 0, 0, dpr, 0, 0)
        }
        context.restore()

        if (contextual && focusId && camera.zoom > 0.48) {
          drawEdgeLabel(edge, a, control, b, 0.92)
        }
        if (contextual && focusId && !reduceMotion) {
          const progress = (time * 0.00013 + edge.seed) % 1
          const packet = curvePoint(a, control, b, progress)
          context.save()
          context.globalAlpha = 0.62
          context.fillStyle = color
          context.shadowColor = color
          context.shadowBlur = 7
          circle(context, packet.x, packet.y, 2.2)
          context.fill()
          context.restore()
        }
      }

      const labelPriority = (node: SimNode) => {
        if (node.id === hoveredIdRef.current) return 130
        if (node.id === propsRef.current.selectedId) return 120
        if (node.primary) return 110
        return {
          page: 90,
          candidate: 80,
          contact: 70,
          transaction: 60,
          offer: 55,
          brand: 50,
          destination: 40,
          other: 30,
        }[node.presentation.visualKind]
      }
      const orderedNodes = [...nodes].sort(
        (left, right) => labelPriority(right) - labelPriority(left)
      )
      const occupiedLabels: Array<{
        left: number
        right: number
        top: number
        bottom: number
      }> = []

      for (const node of orderedNodes) {
        const point = worldToScreen(node, time)
        const radius = node.radius * camera.zoom
        const selected = node.id === propsRef.current.selectedId
        const hoveredNode = node.id === hoveredIdRef.current
        const copy = graphNodeText(node)
        const match =
          !query ||
          `${copy.title} ${copy.subtitle} ${node.label}`
            .toLowerCase()
            .includes(query)
        const related = !focusId || focusSet.has(node.id)
        const alpha = (match ? 1 : 0.16) * (related ? 1 : 0.13)
        const entered = reduceMotion
          ? 1
          : Math.max(0, Math.min(1, (time - node.bornAt) / 260))
        const drawRadius = Math.max(4, radius * entered)
        context.save()
        context.globalAlpha = alpha * entered

        if (selected || hoveredNode) {
          context.shadowColor = node.presentation.color
          context.shadowBlur = selected ? 20 : 13
          circle(context, point.x, point.y, drawRadius + 7)
          context.strokeStyle = rgba(
            node.presentation.color,
            selected ? 0.9 : 0.62
          )
          context.lineWidth = 1.6
          context.stroke()
        }

        circle(context, point.x, point.y, drawRadius)
        context.fillStyle = rgba(
          node.presentation.color,
          node.primary ? 0.2 : 0.12
        )
        context.fill()
        context.lineWidth = node.primary ? 2.2 : 1.45
        context.strokeStyle = node.presentation.color
        if (node.presentation.visualKind === "candidate") {
          context.setLineDash([5, 4])
        }
        context.stroke()
        context.setLineDash([])

        circle(context, point.x, point.y, Math.max(3, drawRadius * 0.73))
        context.fillStyle = "rgba(4, 14, 24, 0.94)"
        context.fill()
        context.strokeStyle = rgba(node.presentation.color, 0.35)
        context.lineWidth = 0.8
        context.stroke()
        context.shadowBlur = 0
        drawGraphIcon(
          context,
          node.presentation.icon,
          point.x,
          point.y,
          Math.max(
            7,
            drawRadius *
              (node.presentation.icon === "telegram" ||
              node.presentation.icon === "whatsapp"
                ? 0.82
                : 0.43)
          ),
          selected || node.primary ? "#f7fbff" : node.presentation.color
        )

        const labelY = point.y + drawRadius + (node.primary ? 24 : 19)
        context.textAlign = "center"
        context.textBaseline = "middle"
        context.font = `${node.primary ? 720 : 650} ${node.primary ? 12 : 10.5}px 'Geist Variable', sans-serif`
        const title = truncate(copy.title, node.primary ? 30 : 24)
        const titleWidth = context.measureText(title).width
        context.font = "500 8.5px 'Geist Variable', sans-serif"
        const subtitleWidth = context.measureText(copy.subtitle).width
        const labelWidth = Math.max(titleWidth, subtitleWidth) + 10
        const labelBounds = {
          left: point.x - labelWidth / 2,
          right: point.x + labelWidth / 2,
          top: labelY - 8,
          bottom: labelY + 22,
        }
        const forcedLabel = selected || hoveredNode || node.primary
        const collides = occupiedLabels.some(
          (placed) =>
            labelBounds.left < placed.right &&
            labelBounds.right > placed.left &&
            labelBounds.top < placed.bottom &&
            labelBounds.bottom > placed.top
        )
        const showLabel = forcedLabel || !collides
        if (showLabel) {
          occupiedLabels.push(labelBounds)
          context.font = `${node.primary ? 720 : 650} ${node.primary ? 12 : 10.5}px 'Geist Variable', sans-serif`
          context.fillStyle = match ? "#edf3f7" : "#687987"
          context.shadowColor = "rgba(0, 0, 0, 0.9)"
          context.shadowBlur = 5
          context.fillText(title, point.x, labelY)
          context.shadowBlur = 0
          context.font = "500 8.5px 'Geist Variable', sans-serif"
          context.fillStyle = related ? "#8797a6" : "#52616d"
          context.fillText(copy.subtitle, point.x, labelY + 14)
        }

        if (copy.badge && camera.zoom > 0.52 && showLabel) {
          context.font = "700 7px 'Geist Variable', sans-serif"
          const badgeWidth = context.measureText(copy.badge).width + 10
          const badgeX = point.x + drawRadius * 0.76
          const badgeY = point.y - drawRadius * 0.68
          context.fillStyle = "rgba(27, 13, 26, 0.96)"
          context.strokeStyle = rgba(node.presentation.color, 0.66)
          context.beginPath()
          context.roundRect(badgeX, badgeY - 7, badgeWidth, 14, 5)
          context.fill()
          context.stroke()
          context.fillStyle = node.presentation.color
          context.textAlign = "left"
          context.fillText(copy.badge, badgeX + 5, badgeY + 0.5)
        }
        context.restore()
      }

      drawMinimap(nodes, edges)
      frame = window.requestAnimationFrame(paint)
    }

    frame = window.requestAnimationFrame(paint)
    return () => window.cancelAnimationFrame(frame)
  }, [isVisible, reduceMotion, worldToScreen])

  const nodeAt = useCallback(
    (x: number, y: number) => {
      const nodes = [...simulationRef.current.values()]
        .filter(isVisible)
        .reverse()
      for (const node of nodes) {
        const point = worldToScreen(node, performance.now())
        const radius = Math.max(15, node.radius * cameraRef.current.zoom + 8)
        if (Math.hypot(x - point.x, y - point.y) <= radius) return node
      }
      return null
    },
    [isVisible, worldToScreen]
  )

  const canvasPoint = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
  }

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const point = canvasPoint(event)
    const node = nodeAt(point.x, point.y)
    event.currentTarget.setPointerCapture(event.pointerId)
    pointerRef.current = {
      id: event.pointerId,
      startX: point.x,
      startY: point.y,
      cameraX: cameraRef.current.targetX,
      cameraY: cameraRef.current.targetY,
      dragId: node?.id,
      moved: false,
    }
    if (node) node.pinned = true
  }

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const point = canvasPoint(event)
    const pointer = pointerRef.current
    if (pointer && pointer.id === event.pointerId) {
      const dx = point.x - pointer.startX
      const dy = point.y - pointer.startY
      pointer.moved ||= Math.hypot(dx, dy) > 3
      if (pointer.dragId) {
        const node = simulationRef.current.get(pointer.dragId)
        if (node) {
          const world = screenToWorld(point.x, point.y)
          node.x = world.x
          node.y = world.y
          node.vx = event.movementX / cameraRef.current.zoom
          node.vy = event.movementY / cameraRef.current.zoom
        }
      } else {
        const camera = cameraRef.current
        camera.targetX = pointer.cameraX - dx / camera.zoom
        camera.targetY = pointer.cameraY - dy / camera.zoom
      }
      setHovered(null)
      hoveredIdRef.current = null
      return
    }
    const node = nodeAt(point.x, point.y)
    hoveredIdRef.current = node?.id ?? null
    setHovered(
      node
        ? {
            node,
            x: Math.min(sizeRef.current.width - 230, point.x + 14),
            y: Math.min(sizeRef.current.height - 76, point.y + 14),
          }
        : null
    )
  }

  const onPointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const pointer = pointerRef.current
    if (!pointer || pointer.id !== event.pointerId) return
    if (pointer.dragId) {
      const node = simulationRef.current.get(pointer.dragId)
      if (node) {
        releaseWithMomentum(node)
        if (!pointer.moved) onSelect(node)
      }
    }
    pointerRef.current = null
  }

  const onPointerLeave = () => {
    hoveredIdRef.current = null
    setHovered(null)
  }

  const onWheel = (event: React.WheelEvent<HTMLCanvasElement>) => {
    event.preventDefault()
    const before = screenToWorld(
      event.nativeEvent.offsetX,
      event.nativeEvent.offsetY
    )
    const camera = cameraRef.current
    camera.targetZoom = Math.max(
      0.28,
      Math.min(2.2, camera.targetZoom * Math.exp(-event.deltaY * 0.0012))
    )
    camera.zoom = camera.targetZoom
    const after = screenToWorld(
      event.nativeEvent.offsetX,
      event.nativeEvent.offsetY
    )
    camera.targetX += before.x - after.x
    camera.targetY += before.y - after.y
  }

  const zoom = (factor: number) => {
    cameraRef.current.targetZoom = Math.max(
      0.28,
      Math.min(2.2, cameraRef.current.targetZoom * factor)
    )
  }

  const visibleNodes = projection.nodes.filter(
    (node) =>
      node.sequence <= playbackCutoff &&
      filters.has(node.presentation.visualKind) &&
      graphLensAllows(node, lens)
  )
  const visibleIds = new Set(visibleNodes.map((node) => node.id))
  const visibleEdges = projection.edges.filter(
    (edge) =>
      edge.sequence <= playbackCutoff &&
      visibleIds.has(edge.source) &&
      visibleIds.has(edge.target)
  )
  const currentLens = GRAPH_LENSES.find((item) => item.key === lens)
  const lensLabel = (key: GraphLens, fallback: string) => {
    if (language !== "id") return fallback
    return { evidence: "Bukti", navigation: "Navigasi", review: "Tinjau" }[key]
  }

  return (
    <section className="graph-panel" aria-label="Evidence relationship graph">
      <div className="graph-toolbar">
        <div className="graph-toolbar-meta">
          <span>{projection.mode}</span>
          <strong>
            {visibleNodes.length} nodes · {visibleEdges.length} observed links
          </strong>
        </div>
        <div
          className="graph-lens-control"
          role="group"
          aria-label="Graph lens"
        >
          {GRAPH_LENSES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={item.key === lens ? "graph-lens-active" : undefined}
              aria-pressed={item.key === lens}
              title={item.description}
              onClick={() => onLensChange(item.key)}
            >
              {lensLabel(item.key, item.label)}
            </button>
          ))}
        </div>
        <div className="graph-toolbar-actions">
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label="Zoom graph out"
                  onClick={() => zoom(0.82)}
                >
                  <MagnifyingGlassMinus />
                </Button>
              }
            />
            <TooltipContent>Zoom out</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label="Zoom graph in"
                  onClick={() => zoom(1.22)}
                >
                  <MagnifyingGlassPlus />
                </Button>
              }
            />
            <TooltipContent>Zoom in</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label="Fit graph"
                  onClick={fitGraph}
                >
                  <CornersOut />
                </Button>
              }
            />
            <TooltipContent>Fit all visible nodes</TooltipContent>
          </Tooltip>
        </div>
      </div>
      <p className="graph-lens-description sr-only" aria-live="polite">
        {language === "id"
          ? lens === "evidence"
            ? "Semua halaman tersimpan dan observasi publik"
            : lens === "navigation"
              ? "Halaman, redirect, dan tujuan yang terhubung"
              : "Kandidat tertunda dan relasi review tersimpan"
          : currentLens?.description}
      </p>
      <div ref={containerRef} className="graph-canvas-wrap">
        <canvas
          ref={canvasRef}
          className="graph-canvas"
          aria-label="Interactive public evidence relationship graph"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={onPointerLeave}
          onWheel={onWheel}
        />
        <canvas ref={minimapRef} className="graph-minimap" aria-hidden="true" />
        {hovered ? (
          <div
            className="graph-tooltip"
            style={{ left: hovered.x, top: hovered.y }}
          >
            <b>{graphNodeText(hovered.node).subtitle}</b>
            <span>{graphNodeText(hovered.node).title}</span>
            <small>
              {language === "id"
                ? "Klik untuk lihat bukti dan sumbernya"
                : "Click to inspect evidence and provenance"}
            </small>
          </div>
        ) : null}
        {!visibleNodes.length ? (
          <div className="graph-empty">
            <span />
            <strong>
              {language === "id"
                ? "Belum ada node di tampilan ini"
                : "No graph nodes in this view"}
            </strong>
            <p>
              {language === "id"
                ? "Aktifkan filter atau geser timeline ke depan."
                : "Enable a graph filter or move the timeline forward."}
            </p>
          </div>
        ) : null}
      </div>
      <div className="graph-accessible-list sr-only">
        <h2>Graph nodes</h2>
        <ul>
          {visibleNodes.map((node) => {
            const copy = graphNodeText(node)
            return (
              <li key={node.id}>
                <button
                  type="button"
                  aria-current={node.id === selectedId ? "true" : undefined}
                  onClick={() => onSelect(node)}
                >
                  {copy.title} — {copy.subtitle}
                </button>
              </li>
            )
          })}
        </ul>
        <h2>Observed relationships</h2>
        <ul>
          {visibleEdges.map((edge) => {
            const source = projection.nodes.find(
              (node) => node.id === edge.source
            )
            const target = projection.nodes.find(
              (node) => node.id === edge.target
            )
            return (
              <li key={edge.id}>
                {source?.label || edge.source} — {edge.relation} —{" "}
                {target?.label || edge.target}
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
