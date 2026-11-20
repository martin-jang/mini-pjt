---
version: alpha
name: Legacy2Next Console (Vercel-inspired)
description: In-app developer console for an AI agent that modernizes legacy web systems. Stark ink-on-near-white product UI inspired by Vercel's dashboard language — calm, dense, engineered. No marketing decoration.

colors:
  primary: "#171717"
  on-primary: "#ffffff"
  ink: "#171717"
  body: "#4d4d4d"
  mute: "#8f8f8f"
  hairline: "#ebebeb"
  hairline-strong: "#d4d4d4"
  canvas: "#ffffff"
  canvas-soft: "#fafafa"
  canvas-soft-2: "#f2f2f2"
  link: "#0070f3"
  running: "#0070f3"
  running-soft: "#e9f2fe"
  success: "#16a34a"
  success-soft: "#eaf7ee"
  warning: "#f5a623"
  warning-soft: "#fff4e0"
  warning-deep: "#ab570a"
  error: "#e5484d"
  error-soft: "#fdecec"
  pending: "#c7c7c7"

typography:
  page-title:
    fontFamily: Geist, "Noto Sans KR", system-ui, sans-serif
    fontSize: 24px
    fontWeight: 600
    lineHeight: 32px
    letterSpacing: -0.6px
  section-title:
    fontFamily: Geist, "Noto Sans KR", system-ui, sans-serif
    fontSize: 16px
    fontWeight: 600
    lineHeight: 24px
    letterSpacing: -0.32px
  body:
    fontFamily: Geist, "Noto Sans KR", system-ui, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
  body-strong:
    fontFamily: Geist, "Noto Sans KR", system-ui, sans-serif
    fontSize: 14px
    fontWeight: 500
    lineHeight: 20px
  caption:
    fontFamily: Geist, "Noto Sans KR", system-ui, sans-serif
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  code:
    fontFamily: Geist Mono, ui-monospace, monospace
    fontSize: 13px
    fontWeight: 400
    lineHeight: 20px

rounded:
  sm: 6px
  md: 8px
  lg: 12px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.sm}"
    height: 36px
    padding: "0px {spacing.md}"
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    borderColor: "{colors.hairline}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.sm}"
    height: 36px
  form-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    borderColor: "{colors.hairline}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    height: 40px
  card:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.hairline}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  status-badge:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.hairline}"
    textColor: "{colors.body}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: "0px {spacing.xs}"
  sidebar-row:
    backgroundColor: "{colors.canvas-soft}"
    activeBackground: "{colors.canvas-soft-2}"
    textColor: "{colors.body}"
    activeTextColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "{spacing.xs} {spacing.sm}"
  log-viewer:
    backgroundColor: "{colors.primary}"
    textColor: "#ededed"
    typography: "{typography.code}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
---

## Overview

Product surface, not marketing. The console lets a consultant paste a legacy URL, watch an agent pipeline run (crawl → analyze → design → generate → verify), approve at two human gates, then inspect the generated React project. It should feel like a mature deployment dashboard: quiet, confident, information-first. Korean UI copy.

The look comes from restraint: near-white page, pure-white cards held by a 1px hairline, ink-black text, and one black primary button per screen. Color appears ONLY to communicate state.

## Colors

- Page `canvas-soft` #fafafa; cards `canvas` #ffffff; inset regions `canvas-soft-2`.
- Text: `ink` for headings and values, `body` for descriptions, `mute` for hints and timestamps.
- Primary action: `primary` #171717 fill, white label. Exactly one per screen.
- State colors (dot + label, or soft background tint for a whole row/banner):
  - running = blue, success = green, waiting for approval = amber, error/blocked = red, pending = gray.
- Links use `link` blue, no underline until hover.

## Typography

- Geist for Latin, Noto Sans KR for Hangul. Weights 400 / 500 / 600 only. Never 700+.
- Titles: sentence-style Korean, negative tracking, no uppercase, no English eyebrow labels above titles.
- Geist Mono ONLY for real technical values: URLs, file paths, commands, log lines, IDs. Never as decoration.

## Layout

- Left sidebar 240px on `canvas-soft` with a right hairline: product name → "새 요청" button → site list (name + status dot) → bottom "질의".
- Top bar 56px, white, bottom hairline: breadcrumb on the left, small user avatar on the right. Nothing else.
- Content column max 960px, generous whitespace: 48px above the page title, 32px between sections, tight 8px between a label and its control.
- Prefer whitespace and hairline dividers over nested boxes. Never put a card inside a card.

## Elevation

- Default: flat card with 1px hairline. Hover/selected: `0 0 0 1px #00000014, 0 1px 2px #0000000a`.
- Menus and dialogs: `0 4px 16px -4px #0000001a` plus hairline. No heavy shadows, no glow, no gradient.

## Do

- One clear primary action per screen, bottom-right of its form.
- Let real content carry the screen: actual URL examples, actual site names, actual step names.
- Show state with a small colored dot + Korean label.
- Use radio cards with a 1px ink border for the selected option.

## Don't

- No decorative monospace English labels (e.g. "AGENT PIPELINE v1.4", "LIVE VALIDATOR", "REQUIRED", "DEPLOY READY").
- No fake version badges, fake system status chips, or fake tech-stack badges.
- No gradients, glows, illustrations, emoji, or stock icons used as decoration.
- No nested bordered boxes, no five identical cards in a row as filler.
- No pill-shaped 100px buttons; app buttons use 6px corners.
- No logos or brand names of other companies.
