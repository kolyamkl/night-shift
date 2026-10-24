// The app's palette and fonts (frontend/src/index.css), so the video looks like MuGuard.
import "@fontsource-variable/pixelify-sans";
import "@fontsource/silkscreen/400.css";
import "@fontsource-variable/source-serif-4";

export const C = {
  bone: "#ecebe5",
  paper: "#f8f7f3",
  mist: "#dcdad1",
  haze: "#c9c7bd",
  stone: "#8b8a85",
  quiet: "#55534d",
  ink: "#0d0d0d",
  signal: "#e2231a",
  signalDeep: "#b3170f",
  signalSoft: "#ff6b61",
};

export const F = {
  pixel: '"Pixelify Sans Variable", "Pixelify Sans", monospace',
  label: '"Silkscreen", "Pixelify Sans Variable", monospace',
  serif: '"Source Serif 4 Variable", Georgia, serif',
};

export const FONT_LOADS = ['700 64px "Pixelify Sans Variable"', '500 32px "Pixelify Sans Variable"', '400 20px "Silkscreen"', '400 20px "Source Serif 4 Variable"'];

// A hard offset shadow and thick border, like the app's px-frame.
export const frame = (border = 6, shadow = 10) => ({
  border: `${border}px solid ${C.ink}`,
  boxShadow: `${shadow}px ${shadow}px 0 ${C.ink}`,
});
