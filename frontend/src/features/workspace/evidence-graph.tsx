import {
  CornersOut,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
} from "@phosphor-icons/react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type {
  GraphEdge,
  GraphNode,
  GraphProjection,
  NodeShape,
  VisualKind,
} from "@/lib/graph"
import { seededUnit } from "@/lib/graph"
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
  lastX: number
  lastY: number
  cameraX: number
  cameraY: number
  dragId?: string
  moved: boolean
}

const CLUSTER_CENTERS: Record<string, { x: number; y: number }> = {
  "Captured pages": { x: -90, y: 0 },
  "Evidence artifacts": { x: -260, y: 80 },
  "Public observations": { x: 220, y: -110 },
  "Pending leads": { x: 290, y: 115 },
  "Linked destinations": { x: 275, y: 75 },
  "Evidence graph": { x: 0, y: 0 },
}

function rgba(hex: string, alpha: number): string {
  const clean = hex.replace("#", "")
  const value = Number.parseInt(clean, 16)
  const red = (value >> 16) & 255
  const green = (value >> 8) & 255
  const blue = value & 255
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}

function shapePath(
  context: CanvasRenderingContext2D,
  shape: NodeShape,
  x: number,
  y: number,
  radius: number
) {
  context.beginPath()
  if (shape === "circle") {
    context.arc(x, y, radius, 0, Math.PI * 2)
    return
  }
  if (shape === "roundSquare") {
    context.roundRect(
      x - radius,
      y - radius,
      radius * 2,
      radius * 2,
      radius * 0.42
    )
    return
  }
  const sides = shape === "hex" ? 6 : 4
  const rotation = shape === "diamond" ? Math.PI / 4 : -Math.PI / 2
  for (let index = 0; index < sides; index += 1) {
    const angle = rotation + (index / sides) * Math.PI * 2
    const px = x + Math.cos(angle) * radius
    const py = y + Math.sin(angle) * radius
    if (index === 0) context.moveTo(px, py)
    else context.lineTo(px, py)
  }
  context.closePath()
}

function edgeColor(edge: GraphEdge, target?: SimNode): string {
  if (edge.appearance === "rejected" || edge.appearance === "hidden")
    return "#ff6577"
  return target?.presentation.color ?? "#718096"
}

function createSimulation(nodes: GraphNode[]): Map<string, SimNode> {
  const buckets = new Map<string, GraphNode[]>()
  for (const node of nodes) {
    const items = buckets.get(node.cluster) ?? []
    items.push(node)
    buckets.set(node.cluster, items)
  }
  const simulation = new Map<string, SimNode>()
  const bornAt = performance.now()
  for (const [cluster, items] of buckets) {
    const center = CLUSTER_CENTERS[cluster] ?? CLUSTER_CENTERS["Evidence graph"]
    items.forEach((node, index) => {
      const angle =
        (index / Math.max(1, items.length)) * Math.PI * 2 +
        seededUnit(node.id) * 0.8
      const ring = 62 + Math.min(190, items.length * 18) + (index % 2) * 34
      const tx = node.primary ? 0 : center.x + Math.cos(angle) * ring
      const ty = node.primary ? 0 : center.y + Math.sin(angle) * ring * 0.72
      simulation.set(node.id, {
        ...node,
        x: node.primary
          ? 0
          : tx * 0.45 + (seededUnit(`${node.id}:x`) - 0.5) * 90,
        y: node.primary
          ? 0
          : ty * 0.45 + (seededUnit(`${node.id}:y`) - 0.5) * 90,
        vx: 0,
        vy: 0,
        tx,
        ty,
        pinned: false,
        bornAt: bornAt + index * 38,
      })
    })
  }
  return simulation
}

export function EvidenceGraph({
  projection,
  selectedId,
  onSelect,
  filters,
  playbackCutoff,
  searchQuery,
}: {
  projection: GraphProjection
  selectedId?: string | null
  onSelect: (node: GraphNode) => void
  filters: ReadonlySet<VisualKind>
  playbackCutoff: number
  searchQuery: string
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
  const sizeRef = useRef({ width: 800, height: 600, dpr: 1 })
  const propsRef = useRef({
    filters,
    playbackCutoff,
    searchQuery,
    selectedId,
    projection,
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
    }
  }, [filters, playbackCutoff, projection, searchQuery, selectedId])

  const isVisible = useCallback((node: SimNode) => {
    const current = propsRef.current
    return (
      node.sequence <= current.playbackCutoff &&
      current.filters.has(node.presentation.visualKind)
    )
  }, [])

  const worldToScreen = useCallback(
    (node: SimNode, time: number) => {
      const camera = cameraRef.current
      const size = sizeRef.current
      const float = reduceMotion
        ? 0
        : Math.sin(time * 0.0012 + seededUnit(node.id) * Math.PI * 2) * 2.4
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
        minX: Math.min(acc.minX, node.x),
        maxX: Math.max(acc.maxX, node.x),
        minY: Math.min(acc.minY, node.y),
        maxY: Math.max(acc.maxY, node.y),
      }),
      { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
    )
    const width = Math.max(180, bounds.maxX - bounds.minX + 150)
    const height = Math.max(160, bounds.maxY - bounds.minY + 150)
    const camera = cameraRef.current
    camera.targetX = (bounds.minX + bounds.maxX) / 2
    camera.targetY = (bounds.minY + bounds.maxY) / 2
    camera.targetZoom = Math.max(
      0.36,
      Math.min(
        1.35,
        Math.min(sizeRef.current.width / width, sizeRef.current.height / height)
      )
    )
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
    const timer = window.setTimeout(fitGraph, 80)
    return () => window.clearTimeout(timer)
  }, [fitGraph, projection])

  useEffect(() => {
    fitGraph()
  }, [filters, fitGraph])

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

    const physics = (delta: number) => {
      const nodes = [...simulationRef.current.values()].filter(isVisible)
      const byId = simulationRef.current
      const edges = propsRef.current.projection.edges.filter((edge) => {
        const source = byId.get(edge.source)
        const target = byId.get(edge.target)
        return (
          edge.sequence <= propsRef.current.playbackCutoff &&
          source &&
          target &&
          isVisible(source) &&
          isVisible(target)
        )
      })
      for (const node of nodes) {
        if (node.pinned) continue
        node.vx += (node.tx - node.x) * 0.00042 * delta
        node.vy += (node.ty - node.y) * 0.00042 * delta
      }
      for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
        const left = nodes[leftIndex]
        for (
          let rightIndex = leftIndex + 1;
          rightIndex < nodes.length;
          rightIndex += 1
        ) {
          const right = nodes[rightIndex]
          let dx = right.x - left.x
          let dy = right.y - left.y
          const distanceSquared = Math.max(180, dx * dx + dy * dy)
          const distance = Math.sqrt(distanceSquared)
          const force = Math.min(0.75, 700 / distanceSquared) * delta
          dx /= distance
          dy /= distance
          if (!left.pinned) {
            left.vx -= dx * force
            left.vy -= dy * force
          }
          if (!right.pinned) {
            right.vx += dx * force
            right.vy += dy * force
          }
        }
      }
      for (const edge of edges) {
        const source = byId.get(edge.source)
        const target = byId.get(edge.target)
        if (!source || !target) continue
        const dx = target.x - source.x
        const dy = target.y - source.y
        const distance = Math.max(1, Math.hypot(dx, dy))
        const desired = 98 + Math.min(50, edge.relation.length)
        const force = (distance - desired) * 0.00024 * delta
        if (!source.pinned) {
          source.vx += (dx / distance) * force
          source.vy += (dy / distance) * force
        }
        if (!target.pinned) {
          target.vx -= (dx / distance) * force
          target.vy -= (dy / distance) * force
        }
      }
      for (const node of nodes) {
        if (node.pinned) continue
        node.vx *= 0.9
        node.vy *= 0.9
        node.x += node.vx * Math.min(1.5, delta / 16)
        node.y += node.vy * Math.min(1.5, delta / 16)
      }
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
      mini.lineWidth = 0.8
      for (const edge of edges) {
        const source = simulationRef.current.get(edge.source)
        const target = simulationRef.current.get(edge.target)
        if (!source || !target) continue
        const a = mapPoint(source)
        const b = mapPoint(target)
        mini.strokeStyle = rgba(edgeColor(edge, target), 0.45)
        mini.beginPath()
        mini.moveTo(a.x, a.y)
        mini.lineTo(b.x, b.y)
        mini.stroke()
      }
      for (const node of nodes) {
        const point = mapPoint(node)
        mini.fillStyle = node.presentation.color
        mini.beginPath()
        mini.arc(point.x, point.y, node.primary ? 3.3 : 2.2, 0, Math.PI * 2)
        mini.fill()
      }
      const camera = cameraRef.current
      const viewportW = sizeRef.current.width / camera.zoom
      const viewportH = sizeRef.current.height / camera.zoom
      mini.strokeStyle = "rgba(239, 39, 111, 0.85)"
      mini.lineWidth = 1
      mini.strokeRect(
        11 + (camera.x - viewportW / 2 - bounds.minX) * scale,
        9 + (camera.y - viewportH / 2 - bounds.minY) * scale,
        viewportW * scale,
        viewportH * scale
      )
    }

    const paint = (time: number) => {
      const delta = Math.min(32, Math.max(1, time - last))
      last = time
      if (!reduceMotion) physics(delta)
      const size = sizeRef.current
      const camera = cameraRef.current
      camera.x += (camera.targetX - camera.x) * 0.12
      camera.y += (camera.targetY - camera.y) * 0.12
      camera.zoom += (camera.targetZoom - camera.zoom) * 0.12
      context.setTransform(size.dpr, 0, 0, size.dpr, 0, 0)
      context.clearRect(0, 0, size.width, size.height)
      const nodes = [...simulationRef.current.values()].filter(isVisible)
      const nodeById = simulationRef.current
      const edges = propsRef.current.projection.edges.filter((edge) => {
        const source = nodeById.get(edge.source)
        const target = nodeById.get(edge.target)
        return (
          edge.sequence <= propsRef.current.playbackCutoff &&
          source &&
          target &&
          isVisible(source) &&
          isVisible(target)
        )
      })
      const query = propsRef.current.searchQuery.trim().toLowerCase()

      for (const edge of edges) {
        const source = nodeById.get(edge.source)
        const target = nodeById.get(edge.target)
        if (!source || !target) continue
        const a = worldToScreen(source, time)
        const b = worldToScreen(target, time)
        const color = edgeColor(edge, target)
        const emphasized = edge.appearance === "solid_emphasized"
        context.save()
        context.strokeStyle = rgba(color, emphasized ? 0.82 : 0.48)
        context.lineWidth = emphasized ? 1.8 : 1.1
        if (edge.appearance === "dashed" || target.status === "lead")
          context.setLineDash([6, 6])
        context.beginPath()
        context.moveTo(a.x, a.y)
        context.lineTo(b.x, b.y)
        context.stroke()
        context.setLineDash([])
        if (!reduceMotion) {
          const progress = (time * 0.00014 + edge.seed) % 1
          const px = a.x + (b.x - a.x) * progress
          const py = a.y + (b.y - a.y) * progress
          context.fillStyle = rgba(color, 0.9)
          context.shadowColor = color
          context.shadowBlur = 8
          context.beginPath()
          context.arc(px, py, emphasized ? 2.3 : 1.6, 0, Math.PI * 2)
          context.fill()
        }
        context.restore()
      }

      const clusterLabels = new Map<string, { x: number; y: number }>()
      for (const node of nodes) {
        const point = worldToScreen(node, time)
        const current = clusterLabels.get(node.cluster)
        if (!current || point.y < current.y)
          clusterLabels.set(node.cluster, point)
      }
      context.save()
      context.fillStyle = "rgba(145, 160, 180, 0.42)"
      context.font = "600 10px 'Geist Variable', sans-serif"
      for (const [label, point] of clusterLabels) {
        context.fillText(label.toUpperCase(), point.x - 16, point.y - 45)
      }
      context.restore()

      for (const node of nodes) {
        const point = worldToScreen(node, time)
        const radius = node.radius * camera.zoom
        const selected = node.id === propsRef.current.selectedId
        const match =
          !query || `${node.label} ${node.kind}`.toLowerCase().includes(query)
        const alpha = match ? 1 : 0.16
        const entered = reduceMotion
          ? 1
          : Math.max(0, Math.min(1, (time - node.bornAt) / 280))
        const drawRadius = Math.max(4, radius * entered)
        context.save()
        context.globalAlpha = alpha * entered
        context.shadowColor = node.presentation.color
        context.shadowBlur = selected ? 28 : node.primary ? 19 : 11
        shapePath(
          context,
          node.presentation.shape,
          point.x,
          point.y,
          drawRadius + (selected ? 3 : 0)
        )
        context.fillStyle = rgba(
          node.presentation.color,
          selected ? 0.24 : 0.12
        )
        context.fill()
        context.lineWidth = selected ? 2.4 : 1.4
        context.strokeStyle = node.presentation.color
        context.stroke()
        shapePath(
          context,
          node.presentation.shape,
          point.x,
          point.y,
          Math.max(3, drawRadius * 0.63)
        )
        context.fillStyle = "rgba(4, 14, 24, 0.92)"
        context.fill()
        context.strokeStyle = rgba(node.presentation.color, 0.52)
        context.stroke()
        context.shadowBlur = 0
        context.fillStyle = "#f8fafc"
        context.textAlign = "center"
        context.textBaseline = "middle"
        context.font = `700 ${Math.max(7, Math.min(10, drawRadius * 0.55))}px 'Geist Variable', sans-serif`
        context.fillText(node.presentation.icon, point.x, point.y + 0.5)
        context.font = `600 ${selected ? 11 : 10}px 'Geist Variable', sans-serif`
        const label = truncate(node.label, selected ? 35 : 25)
        const textWidth = context.measureText(label).width
        const labelY = point.y + drawRadius + 18
        context.fillStyle = "rgba(3, 11, 19, 0.88)"
        context.beginPath()
        context.roundRect(
          point.x - textWidth / 2 - 7,
          labelY - 10,
          textWidth + 14,
          20,
          6
        )
        context.fill()
        context.strokeStyle = rgba(
          node.presentation.color,
          selected ? 0.58 : 0.18
        )
        context.lineWidth = 0.8
        context.stroke()
        context.fillStyle = match ? "#e8edf3" : "#607080"
        context.fillText(label, point.x, labelY)
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
        const radius = Math.max(12, node.radius * cameraRef.current.zoom + 7)
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
      lastX: point.x,
      lastY: point.y,
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
          node.vx = 0
          node.vy = 0
        }
      } else {
        const camera = cameraRef.current
        camera.targetX = pointer.cameraX - dx / camera.zoom
        camera.targetY = pointer.cameraY - dy / camera.zoom
      }
      pointer.lastX = point.x
      pointer.lastY = point.y
      setHovered(null)
      return
    }
    const node = nodeAt(point.x, point.y)
    setHovered(
      node
        ? {
            node,
            x: Math.min(sizeRef.current.width - 220, point.x + 14),
            y: Math.min(sizeRef.current.height - 55, point.y + 14),
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
        node.pinned = false
        if (!pointer.moved) onSelect(node)
      }
    }
    pointerRef.current = null
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
      filters.has(node.presentation.visualKind)
  )
  const visibleIds = new Set(visibleNodes.map((node) => node.id))
  const visibleEdges = projection.edges.filter(
    (edge) =>
      edge.sequence <= playbackCutoff &&
      visibleIds.has(edge.source) &&
      visibleIds.has(edge.target)
  )

  return (
    <section className="graph-panel" aria-label="Evidence relationship graph">
      <div className="graph-toolbar">
        <div>
          <span>{projection.mode}</span>
          <strong>
            {visibleNodes.length} nodes · {visibleEdges.length} links
          </strong>
        </div>
        <div>
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
      <div ref={containerRef} className="graph-canvas-wrap">
        <canvas
          ref={canvasRef}
          className="graph-canvas"
          aria-label="Interactive public evidence relationship graph"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={() => setHovered(null)}
          onWheel={onWheel}
        />
        <canvas ref={minimapRef} className="graph-minimap" aria-hidden="true" />
        {hovered ? (
          <div
            className="graph-tooltip"
            style={{ left: hovered.x, top: hovered.y }}
          >
            <b>{hovered.node.presentation.label}</b>
            <span>{hovered.node.label}</span>
          </div>
        ) : null}
        {!visibleNodes.length ? (
          <div className="graph-empty">
            <span />
            <strong>No graph nodes in this view</strong>
            <p>Enable a graph filter or move the timeline forward.</p>
          </div>
        ) : null}
      </div>
      <div className="sr-only" aria-label="Accessible relationship table">
        <h2>Accessible relationship table</h2>
        <p>
          {projection.nodes.length} nodes and {projection.edges.length} recorded
          links.
        </p>
        <ul>
          {projection.edges.map((edge) => {
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
