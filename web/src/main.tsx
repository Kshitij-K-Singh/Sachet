import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/outfit'
import '@fontsource-variable/space-grotesk'
// Neither Latin face carries Devanagari, and Hindi is this product's primary
// content -- transcripts, quotes and verdicts all come back Devanagari. Without
// this, every Hindi glyph on the page renders in whatever the OS supplies.
import '@fontsource-variable/noto-sans-devanagari'
import './index.css'
import './effects.css'
import App from './App.tsx'
import { PrefsProvider } from './prefs.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PrefsProvider>
      <App />
    </PrefsProvider>
  </StrictMode>,
)
