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
   shows instead. A scrim keeps text contrast safe over the animation. */
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
            patternScale={3.75}
            patternDensity={0.95}
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
