# MProject.furniture Branding System

## Identity

MProject.furniture is a furniture manufacturing software brand. The MP symbol should stay large, geometric, dimensional, and anchored by the neon green furniture plate. Do not round or redraw the MP into a generic monogram.

## Logo Files

- `branding/logo/mproject-logo-dark.svg` - primary dark SaaS/CAD version
- `branding/logo/mproject-logo-light.svg` - light surface version
- `branding/logo/mproject-logo-transparent.svg` - transparent composition for overlays
- `branding/logo/mproject-logo-flat.svg` - minimalist product UI version
- `branding/logo/mproject-logo-monochrome-dark.svg` - dark single-color print/stamp use
- `branding/logo/mproject-logo-monochrome-light.svg` - light single-color use
- `branding/logo/mp-symbol-3d.svg` - standalone 3D symbol
- `branding/logo/mp-symbol-flat.svg` - flat symbol for compact UI

## Typography

Primary UI and logo typography: `Inter`.

Fallback stack:

```css
font-family: Inter, "Segoe UI", Arial, sans-serif;
```

Recommended weights:

- Logo wordmark: 800
- Section headings: 700
- UI labels: 600
- Body text: 400-500

## Color Palette

| Token | Hex | Usage |
| --- | --- | --- |
| Graphite 950 | `#0d141a` | Primary dark background |
| Graphite 900 | `#111820` | Icon background, app shell |
| Graphite 800 | `#202932` | Flat MP symbol |
| Graphite 700 | `#26303a` | Elevated surfaces |
| Steel 500 | `#66717b` | Metal symbol fill |
| Steel 300 | `#a8b1ba` | Secondary text |
| Surface | `#f7fafc` | Light surfaces |
| Neon Green | `#39d353` | Brand accent, furniture plate |
| Green 600 | `#2cc23f` | Light theme accent |
| Green 700 | `#1faa28` | Deep accent/shadow |

## Spacing Rules

- Minimum logo clear space: height of the green MP plate.
- Minimum wordmark width: 220 px.
- Minimum symbol size: 32 px for UI, 96 px for marketing.
- Use 8 px layout rhythm for product UI.
- Keep cards at 8 px radius or less.
- Avoid decorative gradients in operational UI; reserve dimensional lighting for brand/marketing surfaces.

## Usage Examples

Product header:

```html
<img src="/branding/logo/mproject-logo-flat.svg" alt="MProject.furniture" height="40">
```

Dark app shell:

```html
<aside class="mp-brand-panel">
  <img src="/branding/logo/mp-symbol-flat.svg" alt="" width="56">
  <strong>MProject.furniture</strong>
</aside>
```

Primary action:

```html
<button class="mp-primary-action">Create project</button>
```

## Do Not

- Do not replace the MP geometry with a soft rounded icon.
- Do not make `.furniture` white in the primary lockup.
- Do not use purple/blue gradients as brand backgrounds.
- Do not remove the green plate from the main symbol.
