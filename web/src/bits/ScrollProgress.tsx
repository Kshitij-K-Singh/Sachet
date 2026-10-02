/* Reading-progress bar (Rare UI "Scroll Progress"). Pure CSS scroll-driven
   animation, so no scroll listener ever runs. Unsupported browsers simply
   show no bar, which is a safe progressive enhancement. */
export default function ScrollProgress() {
  return (
    <div className="scroll-progress" aria-hidden="true">
      <div className="scroll-progress-bar" />
    </div>
  );
}
