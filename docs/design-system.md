# Bedside Teal — design system

Calm, clinical, trustworthy. No emojis, no heavy gradients, no playful
illustrations. Tokens live in `frontend/app/globals.css` as CSS variables,
remapped into Tailwind v4's `@theme inline` block so they're available as
ordinary utility classes (`bg-primary`, `text-muted`, `rounded-card`, ...).

## Colour

| Token | Hex | Tailwind utility | Use |
| --- | --- | --- | --- |
| Page | `#F4F8F7` | `bg-page` | App background |
| Surface | `#FFFFFF` | `bg-surface` | Cards, panels on the page background |
| Ink | `#0B2E33` | `text-ink` / `bg-ink` | Default text; background for dark sections |
| Card dark | `#133A40` | `bg-card-dark` | Dark cards sitting inside dark sections |
| Primary | `#00808A` | `bg-primary` / `text-primary` | Primary actions, links, step numbers |
| Mint (accent) | `#00C49A` | `bg-mint` / `text-mint` | Progress fills, "filled" states, success |
| Muted | `#5B7478` | `text-muted` | Secondary/helper text |
| Warning | `#D98E04` | `bg-warning` / `text-warning` | Non-critical caution states |
| Danger | `#B83A3A` | `bg-danger` / `text-danger` | **Red flags / escalation only** — never for ordinary errors |

Dark cards (`bg-card-dark`) get a 1px teal border (`border border-primary/40`)
rather than a shadow, to read as calm/flat rather than skeuomorphic.

## Type

- **Headings** — Source Serif 4, weight 600/700, via `next/font/google`. Applied
  automatically to `h1`–`h4` and `.font-heading`; echoes the deck's serif titles.
- **Body** — Noto Sans, with Noto Sans Devanagari, Tamil, Telugu, Bengali,
  Kannada, Gujarati and Malayalam chained as CSS fallbacks (each loaded via its
  own `next/font/google` call, each with its own CSS variable). Ordinary text
  renders in Noto Sans; the browser automatically drops down the chain to
  whichever loaded font actually has the glyphs for a given script, so mixed
  English/Hindi/Tamil/etc. text in the same paragraph all renders correctly
  with no per-language logic needed in components.

Do not hardcode a literal Google Fonts family name in CSS for these - always
reference the `next/font` CSS variable (see `app/layout.js` / `app/globals.css`)
since the loader renames each family internally.

## Shape & spacing

- **12px card radius** everywhere (`rounded-card`).
- Generous whitespace — prefer `p-6`/`p-8` on cards and sections over tight padding.
- **Numbered teal circles** for step flows: a `bg-primary text-white` circle
  (`w-8 h-8 rounded-full flex items-center justify-center font-heading`)
  holding the step number, next to the step's short label.
- **Progress chips** (lifestyle areas): pill-shaped, three states -
  `pending` (muted outline), `filled` (mint fill), `skipped` (muted fill,
  reduced opacity). See `components/ProgressChips.js`.

## Tone

Plain, short, reassuring language. No clinical jargon in patient-facing copy,
no diagnoses, no emojis. Escalation banners are the one place danger red
appears, and they say clearly and calmly what to do next (contact a doctor or
local emergency services) - never alarmist, never vague.
