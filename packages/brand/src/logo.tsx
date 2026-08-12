export function HawkMark({
  imageSrc,
  className = "",
}: {
  imageSrc: string;
  className?: string;
}) {
  return (
    <span className={`hawk-mark ${className}`.trim()} aria-hidden="true">
      <img src={imageSrc} alt="" />
    </span>
  );
}

export function Logo({
  compact = false,
  imageSrc,
}: {
  compact?: boolean;
  imageSrc?: string;
}) {
  if (!imageSrc) return null;
  return (
    <span className="brand-lockup">
      <HawkMark imageSrc={imageSrc} />
      <span>
        <strong>HAWK-EYE</strong>
        {compact ? null : <small>ALAT INVESTIGASI EKOSISTEM JUDI ONLINE</small>}
      </span>
    </span>
  );
}
