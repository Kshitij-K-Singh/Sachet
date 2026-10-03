import { Suspense, lazy, useSyncExternalStore } from "react";

const PixelBlast = lazy(() => import("./PixelBlast"));

function subscribe() {
  return () => {};
}

function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false
  );
}

/* Full-viewport PixelBlast backdrop (React Bits "Pixel Blast", squares,
   brand burnt-orange). Lazy-loaded so the WebGL bundle never blocks first
   paint. Under reduced motion the canvas never mounts; a static field
   shows instead. A scrim keeps text contrast safe over the animation.

   Tuned right down on purpose. It was density 0.95 under a 0.52 scrim, which
   put a near-solid orange dot field behind every word on the page -- it read as
   static rather than texture, and it spent the accent colour as wallpaper.
   That matters beyond taste: #e95a2b carries meaning on this page (the
   product's own voice, and the warning state), and a page-wide field of it
   dilutes exactly the signal the rubric depends on. Atmosphere, not
   attention. */
export default function Backdrop() {
  const reduce = useReducedMotion();

  return (
    <div className="backdrop" aria-hidden="true">
      {!reduce && (
        <Suspense fallback={null}>
          <PixelBlast
            variant="square"
            pixelSize={6}
            color="#e95a2b"
            patternScale={4.4}
            patternDensity={0.34}
            pixelSizeJitter={0.5}
            enableRipples
            rippleSpeed={0.4}
            rippleThickness={0.12}
            rippleIntensityScale={1.5}
            liquid
            liquidStrength={0.12}
            liquidRadius={1.2}
            liquidWobbleSpeed={5}
            speed={0.6}
            edgeFade={0.25}
            transparent
          />
        </Suspense>
      )}
      <div className="backdrop-scrim" />
      <div className="backdrop-vignette" />
    </div>
  );
}
