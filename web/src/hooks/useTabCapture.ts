import { useCallback, useEffect, useRef, useState } from "react";

/* Tab audio capture via navigator.mediaDevices.getDisplayMedia.
 *
 * The product argument for this: someone is watching a reel right now. Link
 * pasting needs a URL, file upload needs a file they have to go and find. This
 * needs neither - one click on the tab they are already watching.
 *
 * It also sidesteps the whole downloader problem: no yt-dlp, no platform login,
 * no cookies, and nothing that breaks when a site changes its markup.
 *
 * Three browser facts shape everything below:
 *
 *  1. `video: true` is mandatory even though we only want audio. Chrome throws
 *     otherwise. We take the audio track and immediately stop the video one.
 *  2. Tab audio is Chrome/Edge only, and needs an explicit "Share tab audio"
 *     tick in the picker. Forget it and the capture is *silent*, not an error -
 *     which is why silence is detected and reported separately (see `peak`).
 *  3. The level meter must not use requestAnimationFrame. During capture the
 *     reel tab is foreground and this one is backgrounded, where rAF is frozen
 *     solid. A setInterval still fires (throttled to ~1 Hz), which is enough to
 *     answer the only question that matters: was there any sound at all.
 */

export type CaptureStatus = "idle" | "requesting" | "recording" | "finishing";

/** Why recording stopped. Each maps to different advice for the user. */
export type StopReason = "timer" | "user" | "share_ended";

export type CaptureErrorCode =
  /** No getDisplayMedia, or no MediaRecorder. Practically: not Chrome/Edge. */
  | "unsupported_browser"
  /** getDisplayMedia requires a secure context: https or localhost. */
  | "insecure_context"
  /** User dismissed the picker or clicked the browser's block control. */
  | "permission_denied"
  /** Picker returned, but no audio track: "Share tab audio" was not ticked. */
  | "no_audio_track"
  /** Stopped before the minimum usable length. */
  | "too_short"
  /** Everything else: hardware, encoder, browser bug. */
  | "device_error";

export interface CaptureError {
  code: CaptureErrorCode;
  /** User-facing, already phrased as an instruction rather than a stack trace. */
  message: string;
}

export interface TabCaptureResult {
  blob: Blob;
  /** Wall-clock length of the recording. */
  durationMs: number;
  /** Highest RMS seen across the clip, 0..1. Drives the silence warning. */
  peak: number;
  reason: StopReason;
  mimeType: string;
}

export interface UseTabCaptureOptions {
  /** Hard cap. Also the countdown the user sees. */
  maxMs?: number;
  /** Below this RMS we call it silence. Tuned by ear; tab audio is quiet. */
  silenceThreshold?: number;
  /** Anything shorter is unusable - whisper needs a moment to lock on. */
  minMs?: number;
  onComplete?: (result: TabCaptureResult) => void;
  onError?: (error: CaptureError) => void;
}

/* Opus in WebM is what Chrome and Edge both produce, and ffmpeg reads it
   directly, so the container never has to be converted server-side. */
const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

export function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return PREFERRED_MIME_TYPES.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

/** Root-mean-square of a time-domain byte buffer, 0..1. 128 is the midpoint.
 *
 *  8-bit PCM is unsigned and offset by the 128 midpoint, so the negative full
 *  scale reaches -1 while the positive only reaches 127/128. A full-scale
 *  square wave therefore measures ~0.996, not 1.0 -- callers should clamp
 *  rather than expect to see exactly 1.
 *
 *  An empty buffer would make this sqrt(0/0) = NaN. NaN fails every comparison
 *  silently, so it would quietly disable the silence check rather than raising.
 */
export function rmsOf(buffer: Uint8Array): number {
  if (buffer.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < buffer.length; i += 1) {
    const v = (buffer[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / buffer.length);
}

/** Maps a rejected getDisplayMedia promise onto actionable copy.
 *
 *  Only handles rejections. Preconditions -- is the API even there, is the page
 *  a secure context -- are checked in `preflight()` before we call, because a
 *  promise from getDisplayMedia cannot reject for a reason that would have
 *  prevented the call in the first place.
 */
export function describeCaptureError(err: unknown): CaptureError {
  const name = err instanceof DOMException ? err.name : "";
  const msg = err instanceof Error ? err.message : String(err);
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return {
      code: "permission_denied",
      message:
        "Screen sharing was blocked or the picker was dismissed. To capture a reel, choose Chrome Tab and tick Share tab audio.",
    };
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return { code: "device_error", message: "No shareable tab or window was found." };
  }
  if (name === "NotReadableError" || name === "AbortError") {
    return {
      code: "device_error",
      message: "The browser stopped the capture before it started. Try again.",
    };
  }
  return {
    code: "device_error",
    message: `Could not start capture (${msg}). Try again, or upload the clip instead.`,
  };
}

/** Checks everything that must hold *before* getDisplayMedia is called.
 *  Returns null when it is safe to proceed. */
export function preflight(): CaptureError | null {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getDisplayMedia) {
    return {
      code: "unsupported_browser",
      message:
        "This browser can't capture tab audio. Use Chrome or Edge on a desktop - Firefox and Safari can't do it.",
    };
  }
  if (typeof MediaRecorder === "undefined") {
    return {
      code: "unsupported_browser",
      message: "This browser has no audio recorder available. Upload a clip instead.",
    };
  }
  if (!canCaptureTabAudio()) {
    // Reached this before it matters: Gecko and WebKit both expose
    // getDisplayMedia and both ignore the audio request, so opening the picker
    // would only ever produce silence.
    const name = browserFamily() === "gecko" ? "Firefox or Zen" : "Safari";
    return {
      code: "unsupported_browser",
      message: `${name} can share a screen but not a tab's audio, so Listen won't work here. Open Sachet in Chrome or Edge, or upload a clip instead.`,
    };
  }
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return {
      code: "insecure_context",
      message:
        "Tab capture needs a secure page. Open Sachet over https, or on localhost - a plain http:// LAN address will not work.",
    };
  }
  return null;
}

export function isTabCaptureSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getDisplayMedia &&
    typeof MediaRecorder !== "undefined" &&
    typeof AudioContext !== "undefined"
  );
}

export type BrowserFamily = "chromium" | "gecko" | "webkit" | "unknown";

/** Engine family, from the UA string.
 *
 *  UA sniffing, which is normally a smell. Here it is the only option: the
 *  Screen Capture spec makes the audio track a MAY -- "the user agent is
 *  allowed not to return audio even if the audio constraint is present" -- so
 *  a browser can expose getDisplayMedia and still never hand over audio, and
 *  nothing in the platform lets you detect that before you ask. Firefox's own
 *  test suite asserts getAudioTracks().length === 0 for {video, audio}.
 *
 *  Order matters: Edge and Opera both impersonate Chrome or Safari in their UA,
 *  and they are the browsers that *do* support tab audio, so they have to be
 *  matched before the engines they disguise themselves as.
 */
export function browserFamily(): BrowserFamily {
  if (typeof navigator === "undefined") return "unknown";
  const ua = navigator.userAgent ?? "";
  if (/Firefox\/|FxiOS\//.test(ua)) return "gecko"; // Firefox, and Zen
  if (/Edg\//.test(ua)) return "chromium"; // Edge
  if (/OPR\//.test(ua)) return "chromium"; // Opera
  if (/Chrom(?:e|ium)\//.test(ua)) return "chromium";
  if (/Safari\//.test(ua)) return "webkit";
  return "unknown";
}

/** Whether this browser can capture tab audio at all.
 *
 *  Distinct from `isTabCaptureSupported`, which additionally requires
 *  AudioContext. That is deliberate: AudioContext only drives the level meter,
 *  which is wrapped in its own try/catch and degrades to "silence unknown". The
 *  capture itself needs no audio graph, so requiring one here would refuse a
 *  browser that could in fact record fine.
 *
 *  Unknown families are allowed through on purpose: a future engine is more
 *  likely to be Chromium-based than not, and blocking it would be the worse
 *  failure. Only engines known to ignore audio are turned away.
 */
export function canCaptureTabAudio(): boolean {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getDisplayMedia) {
    return false;
  }
  const family = browserFamily();
  return family !== "gecko" && family !== "webkit";
}

/** Does this browser's picker offer a "Share tab audio" checkbox?
 *
 *  Only Chromium does. Firefox's picker has no such control, so telling a
 *  Firefox or Zen user to tick it is nonsense advice. */
export function hasTabAudioCheckbox(): boolean {
  return browserFamily() === "chromium";
}

export interface UseTabCapture {
  status: CaptureStatus;
  /** Instantaneous level 0..1 for the meter. Sampled, so it steps. */
  level: number;
  /** Highest level seen so far. The silence check reads this, not `level`. */
  peak: number;
  /** Ms left on the hard cap. */
  remainingMs: number;
  elapsedMs: number;
  error: CaptureError | null;
  /** True once a usable blob exists, i.e. the panel should offer Send. */
  hasClip: boolean;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

export function useTabCapture(options: UseTabCaptureOptions = {}): UseTabCapture {
  const { maxMs = 30000, silenceThreshold = 0.012, minMs = 1500 } = options;

  const [status, setStatus] = useState<CaptureStatus>("idle");
  const [level, setLevel] = useState(0);
  const [peak, setPeak] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [error, setError] = useState<CaptureError | null>(null);
  const [hasClip, setHasClip] = useState(false);

  const recRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const peakRef = useRef(0);
  const startedRef = useRef(0);
  const stopReasonRef = useRef<StopReason>("timer");
  const tickRef = useRef<number | null>(null);
  const capTimerRef = useRef<number | null>(null);

  const opts = useRef({ onComplete: options.onComplete, onError: options.onError });
  opts.current = { onComplete: options.onComplete, onError: options.onError };

  const release = useCallback(() => {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (capTimerRef.current !== null) {
      window.clearTimeout(capTimerRef.current);
      capTimerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => {
      t.onended = null;
      t.stop();
    });
    streamRef.current = null;
    recRef.current = null;
    const ctx = ctxRef.current;
    ctxRef.current = null;
    // Closing is async and can reject if the context never started; ignore.
    void ctx?.close().catch(() => undefined);
    setLevel(0);
  }, []);

  const stop = useCallback(() => {
    const rec = recRef.current;
    if (rec && rec.state !== "inactive") {
      stopReasonRef.current = "user";
      setStatus("finishing");
      rec.stop();
    }
  }, []);

  const reset = useCallback(() => {
    release();
    chunksRef.current = [];
    peakRef.current = 0;
    startedRef.current = 0;
    stopReasonRef.current = "timer";
    setStatus("idle");
    setPeak(0);
    setElapsedMs(0);
    setError(null);
    setHasClip(false);
  }, [release]);

  const start = useCallback(() => {
    if (status === "requesting" || status === "recording") return;
    setError(null);
    setHasClip(false);
    chunksRef.current = [];
    peakRef.current = 0;
    setPeak(0);
    setElapsedMs(0);

    // Everything that can be known before the call, checked before the call.
    const blocked = preflight();
    if (blocked) {
      setStatus("idle");
      setError(blocked);
      return;
    }

    setStatus("requesting");

    // getDisplayMedia must be called from a user gesture; `start` is invoked
    // straight from an onClick handler for exactly that reason.
    void navigator.mediaDevices
      .getDisplayMedia({
        video: true,
        audio: true,
        preferCurrentTab: true,
        selfBrowserSurface: "exclude",
      } as DisplayMediaStreamOptions)
      .then((stream) => {
        const audio = stream.getAudioTracks();
        stream.getVideoTracks().forEach((t) => t.stop());

        if (audio.length === 0) {
          // Silent, not broken. Two very different causes and the advice
          // differs: a Chromium picker that was used without ticking the
          // checkbox, versus an engine that will never give us audio at all.
          // preflight() should have caught the second case already, but a UA
          // check can be wrong, so never tell a non-Chromium browser to look
          // for a checkbox it does not have.
          stream.getTracks().forEach((t) => t.stop());
          setStatus("idle");
          setError(
            hasTabAudioCheckbox()
              ? {
                  code: "no_audio_track",
                  message:
                    "That source had no audio. Pick Chrome Tab again and tick “Share tab audio” at the bottom of the picker.",
                }
              : {
                  code: "unsupported_browser",
                  message:
                    "This browser returned no audio for that tab. Chrome or Edge can capture tab audio; upload a clip instead.",
                }
          );
          return;
        }

        streamRef.current = stream;
        stopReasonRef.current = "timer";

        // Hitting the browser's "Stop sharing" bar ends the track. Per spec
        // MediaRecorder also stops on its own, but relying on that alone has
        // left stuck recorders before, so close it explicitly.
        audio[0].onended = () => {
          stopReasonRef.current = "share_ended";
          const rec = recRef.current;
          if (rec && rec.state !== "inactive") {
            setStatus("finishing");
            rec.stop();
          }
        };

        const mimeType = pickMimeType();
        let rec: MediaRecorder;
        try {
          rec = new MediaRecorder(new MediaStream(audio), mimeType ? { mimeType } : undefined);
        } catch {
          stream.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
          setStatus("idle");
          setError({
            code: "device_error",
            message: "This browser could not start an audio recorder. Upload the clip instead.",
          });
          return;
        }

        recRef.current = rec;
        rec.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
        };

        rec.onstop = () => {
          const durationMs = performance.now() - startedRef.current;
          const peakValue = peakRef.current;
          const reason = stopReasonRef.current;
          const chunks = chunksRef.current;
          release();
          setStatus("idle");
          setElapsedMs(durationMs);
          setPeak(peakValue);

          if (durationMs < minMs) {
            chunksRef.current = [];
            setError({
              code: "too_short",
              message: `That was only ${(durationMs / 1000).toFixed(1)}s - too short to read. Let the reel play for a few seconds, then try again.`,
            });
            return;
          }
          if (peakValue < silenceThreshold) {
            // Recorded fine, heard nothing. Almost always one of three things,
            // and they need different fixes, so name them.
            chunksRef.current = [];
            setError({
              code: "no_audio_track",
              message: hasTabAudioCheckbox()
                ? "No sound was picked up. Either “Share tab audio” was not ticked, or the reel is playing muted — check the volume on the reel tab is up and not muted."
                : "No sound was picked up. The reel may be playing muted — check the volume on that tab is up and not muted.",
            });
            return;
          }

          const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
          chunksRef.current = [];
          if (blob.size === 0) {
            setError({
              code: "device_error",
              message: "The browser produced an empty recording. Try again.",
            });
            return;
          }
          setHasClip(true);
          opts.current.onComplete?.({ blob, durationMs, peak: peakValue, reason, mimeType });
        };

        // Level metering. setInterval, not rAF: see note 3 at the top of file.
        try {
          const ctx = new AudioContext();
          ctxRef.current = ctx;
          void ctx.resume().catch(() => undefined);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 2048;
          // Intentionally not connected to ctx.destination - that would play the
          // captured audio back through the speakers.
          ctx.createMediaStreamSource(new MediaStream(audio)).connect(analyser);
          const buf = new Uint8Array(analyser.fftSize);
          tickRef.current = window.setInterval(() => {
            analyser.getByteTimeDomainData(buf);
            const rms = rmsOf(buf);
            if (rms > peakRef.current) {
              peakRef.current = rms;
              setPeak(rms);
            }
            setLevel(rms);
          }, 120);
        } catch {
          // Metering is a nicety; capture still works without it. Silence
          // detection then degrades to "unknown", which is acceptable.
        }

        startedRef.current = performance.now();
        rec.start();
        setStatus("recording");
        capTimerRef.current = window.setTimeout(() => {
          const r = recRef.current;
          if (r && r.state !== "inactive") {
            stopReasonRef.current = "timer";
            setStatus("finishing");
            r.stop();
          }
        }, maxMs);
        // The elapsed clock runs from an effect keyed on `status`, so it does
        // not belong here.
      })
      .catch((err: unknown) => {
        release();
        setStatus("idle");
        const mapped = describeCaptureError(err);
        setError(mapped);
        opts.current.onError?.(mapped);
      });
  }, [maxMs, minMs, release, silenceThreshold, status]);

  /* Countdown and elapsed clock. A second interval because the level tick is
     also throttled in background tabs and we want the timer to keep moving. */
  useEffect(() => {
    if (status !== "recording") return;
    const id = window.setInterval(() => {
      setElapsedMs(performance.now() - startedRef.current);
    }, 200);
    return () => window.clearInterval(id);
  }, [status]);

  useEffect(() => release, [release]);

  return {
    status,
    level,
    peak,
    remainingMs: Math.max(0, maxMs - elapsedMs),
    elapsedMs,
    error,
    hasClip,
    start,
    stop,
    reset,
  };
}
