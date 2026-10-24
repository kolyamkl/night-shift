# Veil redesign: audit, research and decisions

> Dated design decision log. The current visual rules are in [DESIGN.md](../../DESIGN.md); implemented data boundaries are in [Security](../SECURITY.md).

24 October 2026. Scope: the landing page (`/`) and the app (`/app`) in `frontend/`.

## Audit: why it felt inconsistent and jerky

| Problem | Cause in the code | Fix |
|---|---|---|
| Animations stutter | Almost every transition used `steps()` timing (gate, fan of cards, review bar, wipe). Stepped motion reads as lag outside sprite frames. | Smooth easing and springs for movement; `steps()` only for sprite frame swaps (torch flicker). |
| Messenger and fan jump | The messenger animated `left` (layout on every frame); the fan used stepped transforms with staggered delays. | Animate only `transform`, `opacity` and `clip-path`, driven by Motion values. |
| Gate felt unnatural | A click toggled CSS keyframes with fixed delays, so the state change was not tied to anything the visitor did next. | The gate is part of a scroll-linked scene: it rises as the visitor scrolls, and runs backwards when they scroll up. |
| Two visual languages | Pixel headings next to stock HTML inputs, textareas, buttons and a dashed `border`. Three fonts with no stated roles (Pixelify, Space Mono, Source Serif). | One pixel component set (frame, button, field, card, tabs, chip, spinner, icons) and a two-voice type rule. |
| Decorative knight | The rail and drop zone showed the knight with no job. | Removed. The rail foot now shows whether the redaction model is on. The knight stays only in the approval scene, where it marks the moment the document is safe. |
| Samples were a text list | Labels such as "Tenancy agreement 2" said nothing about the document. | Cards with a pixelated thumbnail of the real first page, a type pictogram, pages and the number of personal values. |
| Landing sections were separate blocks; "Claude" tower | Each section had its own metaphor; the road scene named one provider. | One continuous story on a pinned stage: arrival, the veil, the courier to a neutral "AI provider" tower, the answer coming home. |
| Weak final CTA | "Enter Veil" did not say what happens next. | "Protect a document" opens the app; "Try a sample" opens the app with a tenancy agreement already loading. |

## Research

| Option | What it solves | Fit with React 19, Vite, Tailwind 4 | Cost | Decision |
|---|---|---|---|---|
| [Motion](https://motion.dev/docs/react-use-scroll) 14 (`motion/react`) | Scroll-linked values (`useScroll`, `useTransform`), springs (`useSpring`), `useReducedMotion`, in-view triggers. Uses the browser's ScrollTimeline for GPU-run scroll animations where supported, JS elsewhere. | Native React API. | Tree-shaken; only the hooks and `motion.div` we import. | **Use.** |
| GSAP 3.15 + ScrollTrigger | Timelines and pinning. Free under GSAP's standard licence. | Works via `@gsap/react`, imperative. | Overlaps with Motion; pinning is not needed because CSS `position: sticky` pins the stage. | Not needed. |
| Lenis 1.3 | Smooth (inertial) scrolling. | Fine. | Takes over native scrolling, which the brief rules out (no scroll-jacking). | Not used. |
| CSS scroll-driven animations | Zero-JS scroll animations. | Chrome, Edge and Safari 26+; [not in Firefox](https://caniuse.com/wf-scroll-driven-animations) (Interop 2026). | None. | Not alone; Motion uses the same engine where it exists. |
| [8bitcn/ui](https://github.com/TheOrcDev/8bitcn-ui) (MIT), NES.css, pixel-retroui | Ready pixel components. | 8bitcn needs shadcn, Radix and its own tokens; NES.css is unmaintained since 2022. | Extra dependencies for about eight components. | Borrow the technique (notched pixel frames drawn with box-shadow, a pixel drop shadow that collapses on press), build our own in the Veil palette. |
| Pixel fonts | Readable pixel type at UI sizes. | [Departure Mono](https://departuremono.com/) (OFL) is not on npm; Pixelify Sans (variable) and Silkscreen are on Fontsource. | Self-hosted woff2. | Pixelify Sans for headings and interface text; Silkscreen for labels and numbers. Departure Mono is an option if we download its release files. |

## The system in one rule

Everything Veil says is pixel; everything that is your document is paper.
- Pixel: Pixelify Sans (headings, buttons, fields, messages), Silkscreen (labels, numbers, steps, chips), 4px frames with notched corners, a 4px pixel drop shadow on raised controls, icons drawn on a 16-pixel grid.
- Paper: the document text, pasted text and the AI's answer are set in Source Serif 4 on paper, because they are the user's content.
- Motion: smooth ease-out for movement, springs for scroll-linked scenes, stepped timing only for sprite frames. Every animation has a reduced-motion state.
