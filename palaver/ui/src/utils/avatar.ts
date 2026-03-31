export function getBotAvatarUrl(seed: string, size = 32): string {
  const params = new URLSearchParams({
    seed,
    size: String(size),
    backgroundType: "solid",
    radius: "50",
  });

  return `https://api.dicebear.com/9.x/bottts/svg?${params.toString()}`;
}
