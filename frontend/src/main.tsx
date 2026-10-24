import "@fontsource-variable/pixelify-sans";
import "@fontsource/silkscreen/400.css";
import "@fontsource-variable/source-serif-4";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { SwordCursor } from "./ui/cursor";

// The landing page and the app load separately, so the app does not carry the landing's animation code.
const App = lazy(() => import("./App"));
const inApp = window.location.pathname.startsWith("/app");
const Landing = lazy(() => import("./landing/Landing").then((m) => ({ default: m.Landing })));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={null}>{inApp ? <App /> : <Landing />}</Suspense>
    <SwordCursor calm={inApp} />
  </StrictMode>,
);
