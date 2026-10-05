# Price Check Location — reference page tokens

| Token | Value |
| --- | --- |
| Canvas | Android-first, 412dp wide; vertical `ScrollView`; ignore reference phone/system chrome |
| Background | `#FEFDFA` warm white |
| Primary text | `#012C2D` deep teal |
| Brand green | `#1B713B` |
| Accent orange | `#FF640B` / red-orange pin |
| Card surface | `#FDF6E9` warm cream |
| Main content inset | 24–28dp left/right |
| Card inset | 16–20dp left/right |
| Header | 72–80dp tall; icon-only back target ≥48dp; logo lockup centered |
| Heading | 46–50sp, heavy rounded sans, 52–56sp line height; 3 lines at 412dp |
| Description | 19–20sp, regular/medium, 25–27sp line height; 3 lines at 412dp |
| Hero | 412dp wide, 230–250dp visible height, preserve aspect ratio, no crop of map/pin |
| Choice card | 80–86dp minimum height; radius 24–28dp; very light border/shadow |
| Choice artwork slot | 96–100dp × 64dp; contain; transparent PNG for isolated illustrations |
| Card copy | title 18–20sp semibold/heavy; subtitle 15–16sp regular; 2–4dp vertical gap |
| Card spacing | 10–14dp between cards |
| Scroll/safe area | content may scroll vertically; top and bottom remain inside the shared Safe Area |

## Required copy

- `Find better prices around you`
- `We’ll show you nearby supermarkets and minimarkets with better prices for the items you need.`
- `Use current location` / `See prices near you`
- `Enter an address` / `See prices near an address`

## Font candidates

No font files are present in the project or design directories. The refreshed comparison candidates are `Fredoka Bold`, `Baloo 2 ExtraBold`, and `Nunito ExtraBold`. Bundle and verify the approved candidate before implementation; the temporary QA font files are not project assets.

## Asset provenance

- `location-hero.png`: direct Hero crop from the supplied reference, then a single targeted edit to remove embedded speech-bubble/chalkboard lettering; no new scene generation.
- `current-location.png`: direct card crop with deterministic connected-background removal; RGBA.
- `enter-address.png`: direct card crop with deterministic connected-background removal; RGBA.
- Formal Logo: reuse `/Users/fiona/F5122/wisebasket视觉建议/00_Brand/00_Brand_Logo.jpeg`; do not create another basket mascot or logo lockup.
