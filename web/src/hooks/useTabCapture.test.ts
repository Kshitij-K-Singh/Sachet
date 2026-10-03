/* Tab-capture logic tests.
 *
 * These cover what can be tested without a browser picker: MIME negotiation,
 * the RMS maths behind the silence check, and above all the error mapping -
 * because the single most common real-world failure (the user forgot to tick
 * "Share tab audio") must produce a specific, actionable message rather than a
 * generic one. `getDisplayMedia` cannot be driven headlessly, so the capture
 * loop itself is verified by hand via web/public/capture-spike.html.
 */
import { describe, expect, it } from "vitest";
import {
  browserFamily,
  canCaptureTabAudio,
  describeCaptureError,
  hasTabAudioCheckbox,
  isTabCaptureSupported,
  pickMimeType,
  preflight,
  rmsOf,
} from "./useTabCapture";

/* A byte time-domain buffer is silence at the 128 midpoint. */
const silence = (n: number): Uint8Array => new Uint8Array(n).fill(128);

/* jsdom defines neither MediaRecorder nor AudioContext, and referencing them
   bare throws a ReferenceError. Read and restore them safely. */
function withGlobals<T>(stub: Partial<{ MediaRecorder: unknown; AudioContext: unknown }>, fn: () => T): T {
  const g = globalThis as { MediaRecorder?: unknown; AudioContext?: unknown };
  const before = { mr: g.MediaRecorder, ac: g.AudioContext };
  if ("MediaRecorder" in stub) g.MediaRecorder = stub.MediaRecorder;
  if ("AudioContext" in stub) g.AudioContext = stub.AudioContext;
  try {
    return fn();
  } finally {
    g.MediaRecorder = before.mr;
    g.AudioContext = before.ac;
  }
}

/* navigator.userAgent and navigator.mediaDevices are defined on
   Navigator.prototype, not as own properties of navigator. So
   getOwnPropertyDescriptor returns undefined and a naive restore silently skips,
   leaking a stubbed UA into every later test in the file. Restoring means
   deleting the own property so the prototype lookup takes over again. */
function override<T extends object>(target: T, key: string, value: unknown): () => void {
  const own = Object.getOwnPropertyDescriptor(target, key);
  Object.defineProperty(target, key, { value, configurable: true });
  return () => {
    if (own) Object.defineProperty(target, key, own);
    else delete (target as Record<string, unknown>)[key];
  };
}

function withMediaDevices<T>(value: unknown, fn: () => T): T {
  const restore = override(navigator, "mediaDevices", value);
  try {
    return fn();
  } finally {
    restore();
  }
}

function withUA<T>(ua: string, fn: () => T): T {
  const restore = override(navigator, "userAgent", ua);
  try {
    return fn();
  } finally {
    restore();
  }
}

function withSecureContext<T>(value: boolean, fn: () => T): T {
  const restore = override(window, "isSecureContext", value);
  try {
    return fn();
  } finally {
    restore();
  }
}

describe("rmsOf", () => {
  it("reads digital silence as zero", () => {
    expect(rmsOf(silence(2048))).toBe(0);
  });

  it("reads a full-scale square wave as ~0.996, not 1", () => {
    // 8-bit PCM is unsigned and offset by the 128 midpoint, so the negative
    // full-scale sample hits -1.0 while the positive only reaches 127/128.
    // RMS of that asymmetric pair is sqrt((127^2 + 128^2) / 2) / 128 ~= 0.9961.
    // A naive implementation that assumed symmetric scaling would read 1.0.
    const buf = new Uint8Array(2048);
    for (let i = 0; i < buf.length; i += 1) buf[i] = i % 2 === 0 ? 255 : 0;
    const rms = rmsOf(buf);
    expect(rms).toBeCloseTo(Math.sqrt((127 * 127 + 128 * 128) / 2) / 128, 5);
    expect(rms).toBeLessThan(1);
    expect(rms).toBeGreaterThan(0.99);
  });

  it("scales with amplitude", () => {
    const quiet = new Uint8Array(2048).fill(130); // 2/127 deviation
    const loud = new Uint8Array(2048).fill(160); // 32/127 deviation
    expect(rmsOf(quiet)).toBeLessThan(rmsOf(loud));
    // Roughly 0.016 RMS: under the 0.012-ish quiet threshold band, so a tab
    // sitting at this level is treated as "not really playing".
    expect(rmsOf(quiet)).toBeLessThan(0.02);
  });

  it("is zero for an empty buffer rather than NaN", () => {
    // sqrt(0/0) would be NaN, and NaN fails every comparison silently -- which
    // would quietly disable the silence check instead of raising.
    expect(rmsOf(new Uint8Array(0))).toBe(0);
  });

  it("never returns NaN for any buffer length", () => {
    for (const n of [0, 1, 2, 2048]) {
      expect(Number.isNaN(rmsOf(new Uint8Array(n).fill(200)))).toBe(false);
    }
  });
});

describe("pickMimeType", () => {
  it("prefers Opus in WebM, which is what ffmpeg and hosted STT read directly", () => {
    withGlobals(
      { MediaRecorder: { isTypeSupported: (m: string) => m === "audio/webm;codecs=opus" } },
      () => expect(pickMimeType()).toBe("audio/webm;codecs=opus")
    );
  });

  it("falls back down the list rather than returning nothing early", () => {
    withGlobals(
      { MediaRecorder: { isTypeSupported: (m: string) => m === "audio/webm" } },
      () => expect(pickMimeType()).toBe("audio/webm")
    );
  });

  it("returns empty when nothing is supported, so the browser default applies", () => {
    withGlobals({ MediaRecorder: { isTypeSupported: () => false } }, () =>
      expect(pickMimeType()).toBe("")
    );
  });

  it("returns empty rather than throwing when MediaRecorder is absent", () => {
    withGlobals({ MediaRecorder: undefined }, () => expect(pickMimeType()).toBe(""));
  });
});

const OK_RECORDER = { isTypeSupported: () => true };

describe("browserFamily", () => {
  /* Real UA strings, including Zen, which is a Firefox fork and presents as
     Firefox. Getting this wrong means telling a Zen user to tick a checkbox
     their picker does not have. */
  const UA = {
    zen: "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    firefox: "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    chrome:
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    edge:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0",
    opera:
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/118.0.0.0",
    safari:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
  } as const;


  it("detects Zen as gecko, which is what it is", () => {
    expect(withUA(UA.zen, () => browserFamily())).toBe("gecko");
  });

  it("detects Firefox as gecko", () => {
    expect(withUA(UA.firefox, () => browserFamily())).toBe("gecko");
  });

  it("detects Chrome, Edge and Opera as chromium", () => {
    // Edge and Opera both impersonate Chrome in the UA; matching order must
    // not let them fall through to a generic bucket.
    expect(withUA(UA.chrome, () => browserFamily())).toBe("chromium");
    expect(withUA(UA.edge, () => browserFamily())).toBe("chromium");
    expect(withUA(UA.opera, () => browserFamily())).toBe("chromium");
  });

  it("detects Safari as webkit and not as chromium", () => {
    expect(withUA(UA.safari, () => browserFamily())).toBe("webkit");
  });

  it("does not claim Edge supports audio before checking Chrome's UA", () => {
    // Guards the ordering: if Safari were checked first, Edge's UA would match.
    expect(withUA(UA.edge, () => hasTabAudioCheckbox())).toBe(true);
    expect(withUA(UA.safari, () => hasTabAudioCheckbox())).toBe(false);
  });
});

describe("canCaptureTabAudio", () => {
  const ZEN =
    "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0";
  const CHROME =
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36";


  it("refuses Zen even though getDisplayMedia exists", () => {
    // The bug this guards: Zen exposes the API but ignores the audio request,
    // so an API-only check would show a working button that records silence.
    const supported = withMediaDevices({ getDisplayMedia: () => undefined }, () =>
      withGlobals({ MediaRecorder: OK_RECORDER, AudioContext: class {} }, () =>
        withSecureContext(true, () =>
          withUA(ZEN, () => ({
            api: isTabCaptureSupported(),
            audio: canCaptureTabAudio(),
          }))
        )
      )
    );
    expect(supported.api).toBe(true);
    expect(supported.audio).toBe(false);
  });

  it("allows Chrome and Edge", () => {
    expect(
      withMediaDevices({ getDisplayMedia: () => undefined }, () =>
        withGlobals({ MediaRecorder: OK_RECORDER, AudioContext: class {} }, () =>
          withSecureContext(true, () => withUA(CHROME, () => canCaptureTabAudio()))
        )
      )
    ).toBe(true);
  });

  it("refuses when the API is missing regardless of family", () => {
    expect(
      withMediaDevices({ getDisplayMedia: undefined }, () =>
        withUA(CHROME, () => canCaptureTabAudio())
      )
    ).toBe(false);
  });
});

describe("preflight", () => {
  it("reports unsupported_browser when getDisplayMedia is missing", () => {
    // This is Firefox and Safari. Caught before we ever call.
    const e = withSecureContext(true, () =>
      withMediaDevices({ getDisplayMedia: undefined }, () => preflight())
    );
    expect(e?.code).toBe("unsupported_browser");
    expect(e?.message).toMatch(/chrome or edge/i);
  });

  it("reports insecure_context on a plain http origin", () => {
    const e = withSecureContext(false, () =>
      withMediaDevices({ getDisplayMedia: () => undefined }, () =>
        withGlobals({ MediaRecorder: OK_RECORDER }, () => preflight())
      )
    );
    expect(e?.code).toBe("insecure_context");
    expect(e?.message).toMatch(/https|localhost/i);
  });

  it("passes when everything is present", () => {
    const e = withSecureContext(true, () =>
      withMediaDevices({ getDisplayMedia: () => undefined }, () =>
        withGlobals({ MediaRecorder: OK_RECORDER }, () => preflight())
      )
    );
    expect(e).toBeNull();
  });
});

describe("describeCaptureError", () => {
  it("tells the user to tick the audio checkbox", () => {
    const e = describeCaptureError(new DOMException("Permission denied", "NotAllowedError"));
    expect(e.code).toBe("permission_denied");
    expect(e.message).toMatch(/share tab audio/i);
  });

  it("maps a missing source rather than blaming permissions", () => {
    const e = describeCaptureError(new DOMException("no sources", "NotFoundError"));
    expect(e.code).toBe("device_error");
    expect(e.message).toMatch(/no shareable tab/i);
  });

  it("maps an aborted capture", () => {
    const e = describeCaptureError(new DOMException("stopped", "AbortError"));
    expect(e.code).toBe("device_error");
  });

  it("falls back to a usable message for an unknown error", () => {
    const e = describeCaptureError(new Error("kaboom"));
    expect(e.code).toBe("device_error");
    expect(e.message).toContain("kaboom");
  });

  it("always produces a non-empty message, whatever the exception name", () => {
    for (const name of [
      "NotAllowedError",
      "NotFoundError",
      "NotReadableError",
      "AbortError",
      "InvalidStateError",
      "SomethingNobodyHasHeardOf",
    ]) {
      const e = describeCaptureError(new DOMException("x", name));
      expect(e.message.length).toBeGreaterThan(10);
      expect(e.code).not.toBe("unsupported_browser");
    }
  });
});

describe("isTabCaptureSupported", () => {
  it("is false when getDisplayMedia is missing, i.e. Firefox and Safari", () => {
    expect(withMediaDevices({ getDisplayMedia: undefined }, () => isTabCaptureSupported())).toBe(false);
  });

  it("is false when MediaRecorder is missing", () => {
    expect(
      withMediaDevices({ getDisplayMedia: () => undefined }, () =>
        withGlobals({ MediaRecorder: undefined }, () => isTabCaptureSupported())
      )
    ).toBe(false);
  });

  it("is true when the full API surface is present", () => {
    expect(
      withMediaDevices({ getDisplayMedia: () => undefined }, () =>
        withGlobals({ MediaRecorder: class {}, AudioContext: class {} }, () =>
          isTabCaptureSupported()
        )
      )
    ).toBe(true);
  });
});
