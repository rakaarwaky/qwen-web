---
name: Obsidian Nebula
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0e1c2d'
  surface-container: '#122031'
  surface-container-high: '#1d2b3c'
  surface-container-highest: '#283647'
  on-surface: '#d5e4fa'
  on-surface-variant: '#cfc2d6'
  inverse-surface: '#d5e4fa'
  inverse-on-surface: '#233143'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#b9c8dd'
  on-secondary: '#233142'
  secondary-container: '#39485a'
  on-secondary-container: '#a7b6cb'
  tertiary: '#b9c8de'
  on-tertiary: '#233143'
  tertiary-container: '#8392a6'
  on-tertiary-container: '#1c2b3c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#d4e4fa'
  secondary-fixed-dim: '#b9c8dd'
  on-secondary-fixed: '#0d1d2c'
  on-secondary-fixed-variant: '#39485a'
  tertiary-fixed: '#d4e4fa'
  tertiary-fixed-dim: '#b9c8de'
  on-tertiary-fixed: '#0d1c2d'
  on-tertiary-fixed-variant: '#39485a'
  background: '#051424'
  on-background: '#d5e4fa'
  surface-variant: '#283647'
  terminal-green: '#10B981'
  terminal-red: '#EF4444'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.08em
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin: 24px
---

## Brand & Style

The design system is a high-performance interface optimized for technical environments, balancing the utility of a Terminal User Interface (TUI) with the sophistication of modern engineering tools. It is designed for users who value information density, precision, and a focus-oriented "dark mode" workflow.

The aesthetic is **Modern-Brutalist**. It utilizes sharp geometries, high-contrast borders, and monospaced typography to evoke a sense of computational power. The style avoids organic shapes and soft transitions, favoring a rigid, engineered structure that feels like a refined command center. The emotional response should be one of "digital sovereignty"—total control over complex data.

## Colors

The palette is anchored in a deep, nocturnal blue-black foundation to reduce eye strain during long sessions.

- **Primary (Indigo/Violet):** An energetic bluish-purple used for active states, primary actions, and focus indicators. It represents the "intelligence" layer.
- **Secondary (Deep Navy):** Used for container surfaces and structural layering.
- **Neutral:** A range of grays and slates used for borders and secondary metadata.
- **Support:** Pure white (`#FFFFFF`) is reserved for primary content and commands to ensure peak legibility.

Avoid all use of emojis. Use geometric glyphs or SVG icons for visual signaling.

## Typography

This design system employs a functional dual-font strategy:

1. **Interface/Navigation:** **Geist** is used for headlines and high-level navigation. Its sharp, technical sans-serif terminals complement the system's geometric nature.
2. **Data/Content:** **JetBrains Mono** is the primary driver for all body text, input fields, and code blocks. The monospaced width ensures vertical alignment across rows, reinforcing the grid-based terminal aesthetic.

Maintain a strict 4px baseline rhythm. Section headers should use `label-caps` to act as high-contrast anchors for scanning.

## Layout & Spacing

The layout is governed by a **Fixed-Grid System** inspired by terminal row/column logic.

- **The Grid:** Use a 12-column grid for desktop with 16px gutters. Elements must snap exactly to the grid to maintain an engineered appearance.
- **Density:** High information density is preferred. Use `sm` (12px) padding for internal components.
- **Responsive Behavior:** On mobile, margins reduce to 16px and columns stack. The monospaced typography remains the primary layout driver, even on small screens, to preserve the technical character.

## Elevation & Depth

To remain consistent with the Brutalist-TUI aesthetic, this design system rejects soft shadows and organic depth.

- **Bold Borders:** Use 1px or 2px solid borders to define all surface boundaries.
    - *Default:* Low-contrast gray (`#2c3a4c`).
    - *Focus/Active:* Primary Indigo (`#6366F1`).
- **Tonal Layering:** Depth is communicated through color blocks. Base backgrounds are the darkest, while interactive surfaces or modals use slightly lighter navy tones.
- **Backdrop:** Use a high-opacity (80%) solid dark fill for modal overlays. Avoid background blurs; the underlying content should remain sharp but dimmed.

## Shapes

The shape language is strictly **Sharp (0px)**.

Every UI element—including buttons, input fields, cards, and tags—must have 90-degree corners. This reinforces the rigid, grid-based nature of a developer environment. Icons must follow this geometric constraint, favoring straight lines and sharp angles.

## Components

- **Buttons:** Rectangular with 1px borders. Primary buttons use the Indigo background with white text. Hover states should trigger a "color inversion" (text becomes Indigo, background becomes white/light gray).
- **Input Fields:** Styled as a fully boxed area or an underlined field preceded by a monospaced prompt (e.g., `>`). The active state must feature a non-rounded, blinking block cursor.
- **Chips/Tags:** Small rectangular boxes with 1px borders. Enclose text in brackets for a technical feel (e.g., `[ STATUS: OK ]`).
- **Lists:** Items are separated by subtle 1px horizontal lines. Active selection is indicated by a leading chevron `>` or a full-width background highlight in the secondary color.
- **Cards:** Simple containers defined by a 1px border. Card headers are separated from the body by a 1px horizontal rule.
- **Status Bar:** A persistent 24px tall bar at the bottom of the viewport using the Primary Indigo background to display system metrics and breadcrumbs in high-contrast text.
- **Icons:** Use sharp, geometric SVG icons. **Do not use emojis** for any status or decorative purpose.