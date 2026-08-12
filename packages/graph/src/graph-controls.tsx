export function GraphControls({
  onZoomIn,
  onZoomOut,
  onReset,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}) {
  return (
    <div className="graph-controls" aria-label="Graph view controls">
      <button
        type="button"
        onClick={onZoomIn}
        title="Zoom in"
        aria-label="Zoom in"
      >
        +
      </button>
      <button
        type="button"
        onClick={onZoomOut}
        title="Zoom out"
        aria-label="Zoom out"
      >
        −
      </button>
      <button
        type="button"
        onClick={onReset}
        title="Reset view"
        aria-label="Reset graph view"
      >
        ⌂
      </button>
    </div>
  );
}
