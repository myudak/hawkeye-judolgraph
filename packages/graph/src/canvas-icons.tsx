const WHATSAPP_PATH_DATA =
  "M307.546 52.566C273.709 18.684 228.706.017 180.756 0 81.951 0 1.538 80.404 1.504 179.235c-.017 31.594 8.242 62.432 23.928 89.609L0 361.736l95.024-24.925c26.179 14.285 55.659 21.805 85.655 21.814h.077c98.788 0 179.21-80.413 179.244-179.244.017-47.898-18.608-92.926-52.454-126.807v-.008Zm-126.79 275.788h-.06c-26.73-.008-52.952-7.194-75.831-20.765l-5.44-3.231-56.391 14.791 15.05-54.981-3.542-5.638c-14.912-23.721-22.793-51.139-22.776-79.286.035-82.14 66.867-148.973 149.051-148.973 39.793.017 77.198 15.53 105.328 43.695 28.131 28.157 43.61 65.596 43.593 105.398-.035 82.149-66.867 148.982-148.982 148.982v.008Zm81.719-111.577c-4.478-2.243-26.497-13.073-30.606-14.568-4.108-1.496-7.09-2.243-10.073 2.243-2.982 4.487-11.568 14.577-14.181 17.559-2.613 2.991-5.226 3.361-9.704 1.117-4.477-2.243-18.908-6.97-36.02-22.226-13.313-11.878-22.304-26.54-24.916-31.027-2.613-4.486-.275-6.91 1.959-9.136 2.011-2.011 4.478-5.234 6.721-7.847 2.244-2.613 2.983-4.486 4.478-7.469 1.496-2.991.748-5.603-.369-7.847-1.118-2.243-10.073-24.289-13.812-33.253-3.636-8.732-7.331-7.546-10.073-7.692-2.613-.13-5.595-.155-8.586-.155-2.991 0-7.839 1.118-11.947 5.604-4.108 4.486-15.677 15.324-15.677 37.361s16.047 43.344 18.29 46.335c2.243 2.991 31.585 48.225 76.51 67.632 10.684 4.615 19.029 7.374 25.535 9.437 10.727 3.412 20.49 2.931 28.208 1.779 8.604-1.289 26.498-10.838 30.228-21.298 3.73-10.46 3.73-19.433 2.613-21.298-1.117-1.865-4.108-2.991-8.586-5.234l.008-.017Z";

const TELEGRAM_CIRCLE_PATH_DATA =
  "M128 0C94.06 0 61.48 13.494 37.5 37.49A128.038 128.038 0 0 0 0 128c0 33.934 13.5 66.514 37.5 90.51C61.48 242.506 94.06 256 128 256s66.52-13.494 90.5-37.49c24-23.996 37.5-56.576 37.5-90.51 0-33.934-13.5-66.514-37.5-90.51C194.52 13.494 161.94 0 128 0Z";

const TELEGRAM_PLANE_PATH_DATA =
  "M57.94 126.648c37.32-16.256 62.2-26.974 74.64-32.152 35.56-14.786 42.94-17.354 47.76-17.441 1.06-.017 3.42.245 4.96 1.49 1.28 1.05 1.64 2.47 1.82 3.467.16.996.38 3.266.2 5.038-1.92 20.24-10.26 69.356-14.5 92.026-1.78 9.592-5.32 12.808-8.74 13.122-7.44.684-13.08-4.912-20.28-9.63-11.26-7.386-17.62-11.982-28.56-19.188-12.64-8.328-4.44-12.906 2.76-20.386 1.88-1.958 34.64-31.748 35.26-34.45.08-.338.16-1.598-.6-2.262-.74-.666-1.84-.438-2.64-.258-1.14.256-19.12 12.152-54 35.686-5.1 3.508-9.72 5.218-13.88 5.128-4.56-.098-13.36-2.584-19.9-4.708-8-2.606-14.38-3.984-13.82-8.41.28-2.304 3.46-4.662 9.52-7.072Z";

let whatsappPath: Path2D | undefined;
let telegramCirclePath: Path2D | undefined;
let telegramPlanePath: Path2D | undefined;

function paths() {
  whatsappPath ??= new Path2D(WHATSAPP_PATH_DATA);
  telegramCirclePath ??= new Path2D(TELEGRAM_CIRCLE_PATH_DATA);
  telegramPlanePath ??= new Path2D(TELEGRAM_PLANE_PATH_DATA);
  return { whatsappPath, telegramCirclePath, telegramPlanePath };
}

export type SocialGraphIcon = "telegram" | "whatsapp";

export function drawOfficialSocialIcon(
  context: CanvasRenderingContext2D,
  kind: SocialGraphIcon,
  x: number,
  y: number,
  diameter: number,
) {
  const iconPaths = paths();
  const viewBox =
    kind === "whatsapp"
      ? { width: 360, height: 362 }
      : { width: 256, height: 256 };
  const scale = diameter / Math.max(viewBox.width, viewBox.height);
  context.save();
  context.shadowColor =
    kind === "whatsapp" ? "rgba(37, 211, 102, .72)" : "rgba(42, 171, 238, .72)";
  context.shadowBlur = 10;
  context.translate(
    x - (viewBox.width * scale) / 2,
    y - (viewBox.height * scale) / 2,
  );
  context.scale(scale, scale);
  if (kind === "whatsapp") {
    context.fillStyle = "#25d366";
    context.fill(iconPaths.whatsappPath, "evenodd");
  } else {
    const gradient = context.createLinearGradient(0, 0, 0, 256);
    gradient.addColorStop(0, "#2aabee");
    gradient.addColorStop(1, "#229ed9");
    context.fillStyle = gradient;
    context.fill(iconPaths.telegramCirclePath);
    context.shadowBlur = 0;
    context.fillStyle = "#ffffff";
    context.fill(iconPaths.telegramPlanePath);
  }
  context.restore();
}
