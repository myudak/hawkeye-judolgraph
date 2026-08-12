export function Mascot({
  src,
  alt = "HAWK-EYE mascot",
}: {
  src: string;
  alt?: string;
}) {
  return <img className="he-mascot" src={src} alt={alt} />;
}
