type Size = { width: number; height: number };
type Rect = Size & { left: number; top: number };

export function introPosterLayout(viewport: Size, poster: Size) {
  const scale = Math.min(viewport.width / poster.width, viewport.height / poster.height);
  const width = poster.width * scale;
  const height = poster.height * scale;
  const touchRect = (left: number, top: number, w: number, h: number): Rect => {
    // Expand around the painted control's centre, then keep it inside the poster.
    const touchWidth = Math.min(width, Math.max(44, w * width));
    const touchHeight = Math.min(height, Math.max(44, h * height));
    return {
      left: Math.max(0, Math.min(width - touchWidth, (left + w / 2) * width - touchWidth / 2)),
      top: Math.max(0, Math.min(height - touchHeight, (top + h / 2) * height - touchHeight / 2)),
      width: touchWidth,
      height: touchHeight,
    };
  };
  return {
    width,
    height,
    logo: { left: width * 0.037, top: height * 0.07, width: width * 0.29, height: height * 0.035 },
    skip: touchRect(0.805, 0.06, 0.16, 0.055),
    next: touchRect(0.785, 0.904, 0.17, 0.08),
  };
}
