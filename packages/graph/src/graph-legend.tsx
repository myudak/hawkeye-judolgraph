export function GraphLegend({ language = "id" }: { language?: "id" | "en" }) {
  return (
    <div className="graph-legend" aria-label="Relationship status legend">
      <span>
        <i data-state="verified" />
        {language === "id" ? "Bukti terverifikasi" : "Verified evidence"}
      </span>
      <span>
        <i data-state="pending" />
        {language === "id" ? "Lead tertunda" : "Pending lead"}
      </span>
      <span>
        <i data-state="rejected" />
        {language === "id" ? "Ditolak" : "Rejected"}
      </span>
    </div>
  );
}
