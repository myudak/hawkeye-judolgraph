export const isDemo = import.meta.env.MODE === "demo"

export function publicAssetUrl(name: string): string {
  return isDemo ? `${import.meta.env.BASE_URL}${name}` : `/assets/${name}`
}
