export function GraphLegend() {
  return (
    <div className="graph-legend" aria-label="Relationship status legend">
      <span>
        <i data-state="verified" />
        Verified evidence
      </span>
      <span>
        <i data-state="pending" />
        Pending lead
      </span>
      <span>
        <i data-state="rejected" />
        Rejected
      </span>
    </div>
  );
}
