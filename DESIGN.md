---
name: Veil
description: A redaction desk you watch work, built as one pixel product on bone paper.
colors:
  signal: "#e2231a"
  signal-deep: "#b3170f"
  signal-soft: "#ff6b61"
  ink: "#0d0d0d"
  quiet: "#55534d"
  stone: "#8b8a85"
  haze: "#c9c7bd"
  mist: "#dcdad1"
  bone: "#ecebe5"
  paper: "#f8f7f3"
typography:
  display:
    fontFamily: "Pixelify Sans Variable, Pixelify Sans, ui-monospace, monospace"
    fontSize: "clamp(44px, 7.5vw, 120px)"
    fontWeight: 700
    lineHeight: 1
  hero:
    fontFamily: "Pixelify Sans Variable, Pixelify Sans, ui-monospace, monospace"
    fontSize: "clamp(36px, 4.8vw, 66px)"
    fontWeight: 700
    lineHeight: 1.04
  headline:
    fontFamily: "Pixelify Sans Variable, Pixelify Sans, ui-monospace, monospace"
    fontSize: "clamp(28px, 3vw, 40px)"
    fontWeight: 700
    lineHeight: 1.1
  title:
    fontFamily: "Pixelify Sans Variable, Pixelify Sans, ui-monospace, monospace"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.25
  body:
    fontFamily: "Pixelify Sans Variable, Pixelify Sans, ui-monospace, monospace"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.5
  button:
    fontFamily: "Pixelify Sans Variable, Pixelify Sans, ui-monospace, monospace"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1
  label:
    fontFamily: "Silkscreen, Pixelify Sans Variable, ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "0.04em"
  tag:
    fontFamily: "Silkscreen, Pixelify Sans Variable, ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1
  numeral:
    fontFamily: "Silkscreen, Pixelify Sans Variable, ui-monospace, monospace"
    fontSize: "clamp(40px, 4.6vw, 58px)"
    fontWeight: 400
    lineHeight: 1
    fontFeature: "\"tnum\""
  document:
    fontFamily: "Source Serif 4 Variable, Georgia, serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: "22px"
  field:
    fontFamily: "Source Serif 4 Variable, Georgia, serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
rounded:
  none: "0px"
spacing:
  frame: "4px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "48px"
  section: "80px"
components:
  button-primary:
    backgroundColor: "{colors.signal}"
    textColor: "#ffffff"
    typography: "{typography.button}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "#f03a2f"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
  button-secondary-hover:
    backgroundColor: "#ffffff"
  button-dark:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bone}"
    typography: "{typography.button}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
  button-ghost:
    backgroundColor: "transparent"
    typography: "{typography.button}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
  button-disabled:
    backgroundColor: "{colors.mist}"
    textColor: "{colors.quiet}"
  button-sm:
    padding: "6px 10px"
  button-lg:
    padding: "14px 24px"
  button-xl:
    padding: "18px 30px"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.none}"
    padding: "12px 14px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "4px 8px"
  chip-red:
    textColor: "{colors.signal-deep}"
  chip-dark:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bone}"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "7px 10px"
  tab-hover:
    backgroundColor: "{colors.mist}"
  tab-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bone}"
  session-card:
    backgroundColor: "{colors.bone}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "10px"
  session-card-hover:
    backgroundColor: "{colors.paper}"
  session-card-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bone}"
  sample-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px"
  popover:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px"
  review-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bone}"
    rounded: "{rounded.none}"
    padding: "12px 16px"
  redaction-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.signal-soft}"
    typography: "{typography.tag}"
    rounded: "{rounded.none}"
---

# Design System: Veil

## Overview

**Creative North Star: "Bitmap Bone"**

Veil is one pixel product on bone paper. Everything Veil says, every control, label and message, is drawn in bitmap: pixel type, 4px frames with notched corners, raised buttons that stand on a 4px pixel shadow and sink flat when pressed, icons on a 12-pixel grid. Everything that belongs to the person, their document, the text they paste and the answer an AI gives them, is set in a calm book serif on a paper sheet. The two materials never trade places, so a glance tells you whose words you are reading.

The palette is ink on warm off-white with one signal red. Red means the act of hiding a value or the commit that ends a task (New document, Approve all, Hide, Protect a document). Depth comes from inversion to ink, from pixel frames, and from the hard pixel shadow under things you can press; nothing is blurred and nothing is rounded.

Motion is eased, not stepped. Things that move travel on a soft ease-out or, on the landing story, on a scroll-linked spring that runs backwards when the visitor scrolls up. Stepped timing is kept for sprite frame swaps: torches, pennants, wings, the blinking spinner cells. The signature moment is the line-by-line redaction pass, where each personal value flashes red and a black bar wipes across it and drops a red placeholder tag; the second is the full-screen knight victory after Approve all. The pointer is the guard's sword (`frontend/src/ui/cursor.tsx`), on fine pointers only: native CSS cursor sprites (sword; red-hot blade on clickable things; quill on text fields and in Fix a miss; shield on disabled controls), red embers on a 3px lattice behind a fast swing (the app needs a faster swing and sheds fewer), sparks on click, and an ink tag with a red pixel frame beside the pointer for elements with `data-cursor`. Reduced motion keeps the sprites and drops embers and sparks. The hero castle is a toy (`frontend/src/landing/HeroScene.tsx`): its gate glows and rattles until a press anywhere on the castle opens it on pointer down; documents fly out into a fan (5 on wide screens, 3 under 640px), the visitor slashes the four values of the tenancy agreement in 10 seconds, Veil's guard finishes the rest, every document gets a PROTECTED stamp and the band under the castle shows what the AI provider gets with and without Veil. Every run ends the same way; reduced motion jumps to that end.

**Key Characteristics:**
- Two materials: pixel for Veil's voice, paper and serif for the person's content.
- Bone and paper grounds, ink frames, one signal red for redaction and commit.
- Notched 4px pixel frames on every container and control; 0px radius everywhere.
- Raised pixel buttons with a hard 4px shadow that collapses on press.
- Eased and spring movement; stepped timing only for sprite frames; a reduced-motion state for every animation.
- Icons, pictograms and characters are character-grid sprites with crisp edges.

## Colors

A near-monochrome warm-paper palette with a single hot red that means "this value is being hidden" or "commit".

### Primary
- **Signal Red** (signal): fills the primary button, the flash on a value as it is caught, the 4px gutter change mark, the progress strip, the focus outline, text selection and the caret, the red pixel frame on errors and on a focused field, the active step dot on the landing. Used as a fill, frame or mark, never as small text on light grounds.
- **Deep Signal** (signal-deep): the red that reads as text on bone and paper: error messages, red chips, the popover's placeholder label, a highlighted statistic.
- **Soft Signal** (signal-soft): the red that sits on ink: placeholder tags inside black bars, the fixing prompt in the review bar, a working status on an active session card.

### Neutral
- **Ink** (ink): text, every pixel frame and 4px column rule, black redaction bars, inverted surfaces (review bar, active session card, selected tab, dark button, the landing's final panel and footer), sprite outlines.
- **Quiet** (quiet): secondary text, captions, panel labels, placeholders, the disabled button's text, the shadow under a dark button. Also the sprite steel colour.
- **Stone** (stone): non-text. The disabled button frame, the empty progress track (at 40%), the frame of a pending landing step, knight armour in sprites, confetti.
- **Haze** (haze): sprite and scene colour only (far hills and shading in the landing art).
- **Mist** (mist): tab hover, the disabled button fill, the step-dot ground, the sample card's thumbnail well, the landing's ground band.
- **Bone** (bone): the app and landing ground: rail, intake, document pane, Ask panel, victory sheet, top bar.
- **Paper** (paper): the sheet. Document, sample cards, fields, popovers, settled status bars, secondary buttons, chat answers. A half step lighter than bone so content reads as the page on the desk.

### Named Rules
**The One Red Rule.** Signal red means redaction or commitment. It never decorates and never marks a category, and there is no second accent hue.

**The Red-On-Ink Rule.** On ink, red text is Soft Signal; on bone or paper, red text is Deep Signal. Full Signal is for fills, frames and marks.

## Typography

**Interface Font:** Pixelify Sans Variable (with ui-monospace, monospace)
**Label Font:** Silkscreen 400 (with Pixelify Sans Variable, ui-monospace, monospace)
**Paper Font:** Source Serif 4 Variable (with Georgia, serif)

**Character:** A chunky, readable bitmap face for everything Veil says, a tiny all-caps bitmap for labels and numbers, and a book serif for the human text Veil is protecting.

### Hierarchy
- **Display** (Pixelify 700, clamp 44px to 120px, line-height 1): the victory title only.
- **Hero** (Pixelify 700, clamp 36px to 66px, line-height 1.04, balanced, max 21ch): the landing headline.
- **Headline** (Pixelify 700, clamp 28px to 40px): section headings on the landing and the intake heading; the final call to action runs up to 56px. Sub-headings drop to 24px.
- **Title** (Pixelify 700, 22px): the open file's name, the dropzone prompt, step captions on the landing (24px to 34px).
- **Body** (Pixelify 500, 15px, line-height 1.5): the whole interface: messages, status lines, chat questions, card titles (600, 14px to 16px). Ledes run 16px to 19px in quiet, capped at 52ch to 64ch.
- **Button** (Pixelify 600, 15px, line-height 1): sentence case. 13px small, 20px large, 26px extra large.
- **Label** (Silkscreen 400, 11px, uppercase, 0.04em): panel and field labels, chips, tabs, top bar links, step numbers. 10px for stage labels and meta lines.
- **Tag** (Silkscreen 400, 10px, line-height 1): the placeholder written inside a redaction bar.
- **Numeral** (Silkscreen 400, tabular figures): statistics on the landing (40px to 58px), the training counter (20px), review totals (12px), line numbers (10px).
- **Document** (Source Serif 4, 15px, 22px line): document lines. Short all-caps lines in a document are its own headings: serif 600, 13px, tracked 0.06em.
- **Field** (Source Serif 4, 16px, line-height 1.55): text typed or pasted into a field. Placeholders stay in Pixelify, because a placeholder is Veil talking.
- **Answer** (Source Serif 4, 14px to 15px, relaxed): AI answers, the text sent to the AI, popover values, sample titles (13px), the victory subline (18px, max 56ch).

### Named Rules
**The Pixel and Paper Rule.** Everything Veil says is pixel: Pixelify Sans for headings, interface text, buttons and messages, Silkscreen for labels and numbers. Everything that is the user's document, pasted text or the AI's answer is paper: Source Serif 4. Never set a control in the serif, and never set the person's content in a pixel face.

**The Tabular Count Rule.** Every live count (change counter, review totals, line numbers, statistics, training examples) is Silkscreen with tabular figures.

## Layout

The app is a desk of columns separated by 4px ink rules, each scrolling on its own inside a full-height viewport.

- **1280px and up:** rail 270px, document fills; after approval an Ask panel of 400px opens on the right.
- **1024px to 1279px:** rail 240px, document fills, Ask panel 340px.
- **Below 1024px:** the columns stack as rows (rail, document at least 70vh, Ask panel at least 420px) and the column rules turn into top and bottom rules.

Rhythm runs on a 4px base, which is also the frame weight. Controls pad 6px to 18px vertically; cards and panels pad 10px to 20px; groups sit 8px to 24px apart; landing sections breathe at 80px top and bottom inside a 1152px column. The intake splits the dropzone and the paste field roughly 1.35 to 1, with sample cards in an auto-fill grid of at least 210px and 24px gaps. The document sheet is capped at 860px (page images at 760px). Document lines are a fixed grid: 48px line number, 12px gutter mark, text, 30px minimum row. Status bars float 16px in from the document pane's edges and the pane reserves 176px at its foot so the last line clears them.

The landing is one scroll story: a sticky 64px top bar, a centred hero over a parallax castle scene, a pinned stage (460vh of scroll) that tells four steps, then alternating bone and paper sections and an ink finale. Below the stage's minimum scale the camera pans along the action instead of shrinking it further.

## Elevation & Depth

Flat surfaces, framed and inverted. A container is lifted out of the ground by a pixel frame and a change of ground (paper on bone, ink on bone), never by blur. The one cast shadow is a hard pixel shadow with zero blur under things you can press, and it tells you about the press: it grows by 2px on hover as the control rises, and collapses to nothing as the control sinks 4px on press. Overlays stack by z-order (status bars 20, popovers 30, top bar 40, victory 50).

### Shadow Vocabulary
- **Pixel drop** (`filter: drop-shadow(0 4px 0 ink)`): under every raised button at rest; 6px with a 2px rise on hover; 0px with a 4px sink on press. Dark buttons cast a quiet shadow; buttons on an ink panel cast #45443f.
- **Card lift** (`filter: drop-shadow(0 6px 0 ink)` with a 4px rise): a pressable card on hover or focus (sample cards).
- **Current-line rule** (`box-shadow: inset 0 2px signal, inset 0 -2px signal`): not a lift; the 2px red rules above and below the line being redacted.

### Named Rules
**The Press Rule.** A hard pixel shadow means "you can press this". It belongs only to buttons and pressable cards, it has zero blur, and it collapses when pressed.

**The Inversion Rule.** To raise a surface, frame it or invert it to ink. Never lift it with a soft shadow or a blur.

## Shapes

Square everywhere: 0px radius on every surface, control, bar and sprite. The signature edge is the notched pixel frame: a 3 by 3 pixel image with empty corners stretched over a 4px border (2px on chips, tabs, thin panels and landing steps), so every box reads as drawn on a pixel grid. Frames come in ink, red (errors, focused fields), stone (disabled, pending) and bone (an idle session card that blends into the rail until hover). Column and section rules are plain 4px ink lines. The dropzone border is drawn as 8px ink dashes on a 4px line, turning red while a file is held over it.

Sprites are SVG paths drawn from character grids, one path per colour, with crisp edges at whole-number scales: interface icons on a 12-pixel grid at 2x (3x in large buttons, 5x in the dropzone), document pictograms on a 16-pixel grid at 2x, landing sprites at 4x to 6x, the castle and the victory knight at a fitted whole-pixel size. The grid alphabet is k ink, r signal, g stone, s quiet, w paper, h haze, m mist, c currentColor; icons draw in currentColor so they take their control's text colour. Progress is a segmented strip of 4px blocks with 2px gaps.

### Named Rules
**The Whole Pixel Rule.** Sprites scale only by whole numbers and render with crisp edges. No anti-aliased or fractionally scaled sprite at rest.

**The Notched Frame Rule.** Containers and controls take the notched pixel frame, not a CSS border with square corners. Plain rules are for dividing columns and sections only.

## Components

### Buttons
Tactile pixel keys. Every button has a 4px notched ink frame, Pixelify 600 in sentence case, an optional 12-pixel icon 10px from the label, and the collapsing pixel drop.
- **Primary:** signal fill, white text; hover brightens to #f03a2f. For the commit on a screen: New document, Approve all, Hide, Choose a file, Protect a document.
- **Secondary (default):** paper fill, ink text; hover to white. Prev, Next, Fix a miss, Not personal, show it, Try a sample.
- **Dark:** ink fill, bone text, quiet shadow. Hide personal data, Download redacted.
- **Ghost:** no frame, no shadow, no movement; hover lays a 12% wash of the current text colour. Close, Decline, Show all.
- **Sizes:** small (13px, 6px by 10px), medium (15px, 10px by 16px), large (20px, 14px by 24px, 3x icons), extra large (26px, 18px by 30px).
- **Hover / Focus / Press:** rise 2px on a soft ease-out over 0.14s, sink 4px in 0.05s on press. Focus is a 3px signal outline, offset 6px on buttons and 3px elsewhere. Loading swaps the icon for the pixel spinner. Disabled turns mist with quiet text, a stone frame and no shadow.

### Chips
- **Style:** 2px notched ink frame, no fill, Silkscreen 11px uppercase, 4px by 8px. Counts, file types, page counts, document state.
- **Variants:** red (red frame, Deep Signal text) for review state, value counts and warnings; dark (ink fill, bone text) for an approved document.

### Tabs
Silkscreen 11px uppercase segments, each with a 2px notched frame and 4px apart. Hover fills mist; the selected tab inverts to ink. Used for the Lines and Pages view of a PDF.

### Cards / Containers
- **Corner Style:** square, 4px notched frame (2px for thin panels).
- **Background:** paper on bone for content; ink for the review bar, the user's question and the landing's regulator quote.
- **Shadow Strategy:** none at rest; only pressable cards lift (see Elevation).
- **Sample card:** a mist well with a pixelated thumbnail of the real first page, a 16-pixel pictogram badge, an ink "Open sample" strip that slides up on hover, the title in Pixelify and the subtitle in serif, then chips. On hover the card rises 4px and the thumbnail 6px.
- **Session card:** a 36px pictogram well, the filename in Pixelify 600, a status chip or spinner. Idle cards wear a bone frame, hover turns paper with an ink frame, the active card inverts to ink.

### Inputs / Fields
- **Style:** 4px notched ink frame around a paper well; typed text in the serif at 16px; a Silkscreen label 8px above and a quiet 12px hint below.
- **Focus:** the frame turns red; no glow.
- **Disabled / Error:** errors sit in a paper panel with a red frame and Deep Signal text.

### Navigation
- **App rail:** the Veil wordmark in Pixelify 700 at 38px, the primary New document button at full width, a "Sessions" label, session cards, and a thin-framed paper box at the foot showing whether the redaction model is on (a 10px red or stone square).
- **Landing top bar:** sticky, 64px, bone at 92% until scrolled, then solid with a 4px ink rule. Links in Silkscreen grow a 3px red underline from the left on hover and focus; a small primary button leads into the app.

### Spinner
Three 5px squares in currentColor that blink in turn (0.9s, 0.15s apart). The only loading indicator; it replaces a button's icon while loading.

### Redaction bar and the line-by-line pass (signature)
While the model reads, every line pulses a 5% ink wash on an ease-in-out, staggered 40ms per line, and the progress strip crawls. The pass then advances one line per tick (6000ms divided by the line count, clamped between 70ms and 380ms). The current line gets a 9% red wash with 2px red rules above and below; its values flash solid signal with struck-through white text, then a black bar wipes across left to right on a soft ease-out over 0.38s and the Silkscreen placeholder tag fades in, in Soft Signal. A passed line grows its 4px red gutter mark. Live bars take a 3px signal outline on hover or focus. A real value put back into an AI answer carries a 15% red wash and a 2px red underline.

### Review bar (signature)
An ink panel with a 4px frame docked 16px in from the foot of the document. It rises from below on an expo ease-out over 0.5s once the pass ends. A status line on top (bone at 85%, or Soft Signal while fixing a miss), then the totals in Silkscreen tabular figures, then small secondary buttons (Prev, Next, Fix a miss), a ghost Decline and the primary Approve all. After approval or decline it is replaced by a paper bar carrying the outcome and, on approval, a dark Download button.

### Popovers
Paper panels with a 4px notched frame and 12px padding, opened 10px below the clicked value or selection and easing in 6px over 0.18s. The value popover shows the placeholder as a Deep Signal label, the real value in the serif, a quiet note, and small buttons. The selection popover is one row: the quoted selection in the serif, a type select, and a small primary Hide.

### Victory (signature)
A full-screen bone sheet with a 6px ink dot grid that wipes down over 0.4s. Pixels fly in from all sides and assemble the knight on an expo ease-out; a hacker sprite rises and taunts; the knight drives his sword down at 1.75s; dust kicks out and confetti in ink, signal and stone falls. The title reveals from 2.35s, the serif subline and Continue follow. Click, Enter or Escape dismisses; it closes itself after 8s.

### Landing story (signature)
A pinned stage that tells four steps as the visitor scrolls, driven by a spring on scroll progress (stiffness 140, damping 30, mass 0.35) so it eases and reverses on scroll up. Steps sit above it as 2px-framed pills: pending in stone, current inverted to ink with a red number, done framed in ink. Captions fade and rise 10px on change. With reduced motion the finished scene is shown with the four steps as a list.

## Do's and Don'ts

### Do:
- **Do** set everything Veil says in Pixelify Sans or Silkscreen, and everything that is the user's document, pasted text or the AI's answer in Source Serif 4.
- **Do** frame containers and controls with the notched pixel frame (4px, 2px for chips, tabs and thin panels) and keep every corner at 0px.
- **Do** give every button the 4px pixel drop that rises on hover and collapses on press; reserve the hard shadow for things you can press.
- **Do** move things with eased or spring motion (soft ease-out cubic-bezier(0.22, 0.8, 0.2, 1) for state changes, expo ease-out for arrivals, springs for scroll-linked scenes), animating only transform, opacity and clip-path.
- **Do** use stepped timing only for sprite frame swaps (torches, pennants, wings, spinner cells, a two-frame idle).
- **Do** give every animation a reduced-motion state: the pass resolves instantly, CSS animations collapse to their end state, and scroll scenes show their finished frame.
- **Do** keep signal red for redaction marks and commit actions, with Deep Signal for red text on light grounds and Soft Signal for red on ink.
- **Do** draw icons, pictograms and characters as character-grid sprites at whole-number scales, in currentColor inside controls.
- **Do** use Silkscreen with tabular figures for every live count.

### Don't:
- **Don't** add blurred or soft shadows, glows, backdrop blurs or rounded corners to any surface.
- **Don't** put a hard pixel shadow or a hover lift on anything that cannot be pressed.
- **Don't** animate movement with `steps()`; stepped movement reads as lag outside sprite frames.
- **Don't** set controls, labels or messages in the serif, or the person's content in a pixel face.
- **Don't** introduce a second accent hue or use red decoratively.
- **Don't** set small text in full Signal on bone or paper; it does not reach 4.5:1.
- **Don't** use stone or haze for text; they are fill, frame and sprite colours.
- **Don't** use icon fonts or vector line icons; icons are pixel sprites.
- **Don't** put a Silkscreen label above a headline as a kicker; labels name a field, a panel or a stage element.
