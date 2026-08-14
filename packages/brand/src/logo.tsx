export function HawkMark({
  imageSrc,
  lightImageSrc,
  className = "",
}: {
  imageSrc: string;
  lightImageSrc?: string;
  className?: string;
}) {
  return (
    <span className={`hawk-mark ${className}`.trim()} aria-hidden="true">
      <img className="theme-asset-dark" src={imageSrc} alt="" />
      {lightImageSrc ? (
        <img className="theme-asset-light" src={lightImageSrc} alt="" />
      ) : null}
    </span>
  );
}

export function Logo({
  compact = false,
  imageSrc,
  lightImageSrc,
}: {
  compact?: boolean;
  imageSrc?: string;
  lightImageSrc?: string;
}) {
  if (!imageSrc) return null;
  return (
    <span className="brand-lockup">
      <HawkMark imageSrc={imageSrc} lightImageSrc={lightImageSrc} />
      <span>
        <strong>HAWK-EYE</strong>
        {compact ? null : <small>ALAT INVESTIGASI EKOSISTEM JUDI ONLINE</small>}
      </span>
    </span>
  );
}
