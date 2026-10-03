import { useState } from "react";
import type { ReactElement } from "react";
import { MicrophoneSlash, SpeakerHigh, Waveform } from "@phosphor-icons/react";
import { useTabCapture, browserFamily, canCaptureTabAudio } from "../hooks/useTabCapture";
import type { CaptureError as TabCaptureError, TabCaptureResult } from "../hooks/useTabCapture";
import { usePrefs } from "../prefs-context";

interface ListenPanelProps {
  /** Called with a recorded webm/opus clip. The parent owns sending + errors. */
  onClip: (result: TabCaptureResult) => void;
  /** True while the parent is uploading / transcribing. */
  busy: boolean;
  maxMs?: number;
}

/* "Listen to the tab you're watching."
 *
 * The flow is deliberately two steps, matching the existing audio-upload and
 * screenshot paths: capture and transcribe, then the transcript lands in the
 * textarea for review, then the user analyses. That review step matters MORE
 * here than elsewhere, not less - tab audio is the noisiest input the app
 * takes (background music, room noise, autoplay-ad overlap) and whisper-base
 * will occasionally mishear it. A verdict computed on an unreviewed transcript
 * is exactly what the rest of this app is designed to avoid.
 */
/* The hook returns English prose. It is a pure function with its own test suite
   and no access to React context, so rather than thread a translator through it
   we map its stable error codes to dictionary keys here. Anything unmapped
   falls back to the hook's own English, so a new code can never blank the UI. */
const CAPTURE_ERROR_KEYS: Record<string, string> = {
  permission_denied: "tab.errDenied",
  device_error: "tab.errNone",
  no_audio_track: "tab.errEmpty",
  unsupported_browser: "tab.errNoRecorder",
  insecure_context: "tab.errNoAudioApi",
  too_short: "tab.errTooShort",
};

function captureErrorText(t: (k: string, v?: Record<string, string | number>) => string, err: TabCaptureError): string {
  const key = CAPTURE_ERROR_KEYS[err.code];
  return key ? t(key) : err.message;
}

export default function ListenPanel({ onClip, busy, maxMs = 30000 }: ListenPanelProps): ReactElement {
  const { t } = usePrefs();
  const [note, setNote] = useState<string | null>(null);
  const cap = useTabCapture({
    maxMs,
    onComplete: (r) => {
      setNote(null);
      onClip(r);
    },
  });

  const recording = cap.status === "recording";
  const requesting = cap.status === "requesting";
  const finishing = cap.status === "finishing";
  const live = recording || requesting || finishing;

  /* How far along the capture is, and whether we have actually heard anything.
     peak is the reliable signal; level is only a live hint. */
  const progress = Math.min(100, (cap.elapsedMs / maxMs) * 100);
  const heardSomething = cap.peak > 0.012;
  const secsLeft = Math.ceil(cap.remainingMs / 1000);

  /* Single source of truth for "can this browser do it at all" lives in the
     hook, next to the feature detection it mirrors. Note this is NOT just an
     API check: Firefox and Zen expose getDisplayMedia but ignore the audio
     request, so they get the same answer as Safari rather than a button that
     can only ever record silence. */
  const unsupported = !canCaptureTabAudio();

  function onStart() {
    setNote(null);
    cap.start();
  }

  return (
    <div className="listen">
      <div className={`listen-box ${live ? "live" : ""}`}>
        <span className="listen-icon" aria-hidden="true">
          {live ? <Waveform size={18} weight="bold" /> : <SpeakerHigh size={18} weight="bold" />}
        </span>

        <div className="listen-main">
          {unsupported ? (
            <>
              <strong>
                {browserFamily() === "gecko" ? t("tab.gecko.title") : t("tab.unsupported.title")}
              </strong>
              <small>
                {browserFamily() === "gecko" ? t("tab.gecko.body") : t("tab.other.body")}
              </small>
            </>
          ) : live ? (
            <>
              <strong>
                {requesting
                  ? t("tab.picker")
                  : finishing
                    ? t("tab.wrapping")
                    : t("tab.listeningLeft", { n: secsLeft })}
              </strong>
              <small>
                {requesting ? t("tab.permission") : t("tab.playFirst")}
              </small>
            </>
          ) : (
            <>
              <strong>{t("tab.title")}</strong>
              <small>
                {t("tab.records", { n: Math.round(maxMs / 1000) })}
              </small>
            </>
          )}

          {recording && (
            <div className="listen-meter" role="meter" aria-valuenow={Math.round(cap.level * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={t("tab.level")}>
              <div className="listen-meter-fill" style={{ width: `${Math.min(100, cap.level * 320)}%` }} />
              <div className="listen-meter-tick" style={{ left: `${progress}%` }} />
            </div>
          )}
        </div>

        {!live ? (
          <button type="button" className="listen-go" onClick={onStart} disabled={busy}>
            <SpeakerHigh size={16} weight="bold" />
            {t("tab.listen")}
          </button>
        ) : (
          <button type="button" className="listen-go stop" onClick={cap.stop} disabled={requesting || finishing}>
            <MicrophoneSlash size={16} weight="bold" />
            {t("tab.stop")}
          </button>
        )}
      </div>

      {recording && (
        <p className={`listen-status ${heardSomething ? "heard" : "quiet"}`}>
          {heardSomething
            ? t("tab.listening")
            : t("tab.silent")}
        </p>
      )}

      {cap.error && (
        <p className="listen-error" role="alert">
          {captureErrorText(t, cap.error)}
        </p>
      )}
      {note && <p className="listen-note">{note}</p>}

      <p className="listen-consent">
        {t("tab.consent")}
      </p>
    </div>
  );
}
