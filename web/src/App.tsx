import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import {
  ArrowSquareOut,
  Check,
  Copy,
  Flag,
  Globe,
  Image as ImageIcon,
  LinkSimple,
  Microphone,
  Moon,
  Sun,
} from "@phosphor-icons/react";
import Backdrop from "./bits/Backdrop";
import Magnet from "./bits/Magnet";
import ScrollProgress from "./bits/ScrollProgress";
import SplitText from "./bits/SplitText";
import Card from "./ui/Card";
import ListenPanel from "./ui/ListenPanel";
import Logo from "./ui/Logo";
import Meter from "./ui/Meter";
import { usePrefs } from "./prefs-context";
import { makeT, type Lang } from "./i18n";
import type { TabCaptureResult } from "./hooks/useTabCapture";
import "./App.css";

/* ------------------------------------------------------------------ types
   Mirrors api/main.py AnalyzeResponse. Keep in sync; contract v1. */

/* Two axes, mirroring the API.
   scope  -> is this the kind of thing we judge at all?
   label  -> promotion | educational   (the conclusion, if any)
   "mixed" is label=educational with a non-empty red_flags list: mostly
   teaching, one persuasion tactic present. */
type Scope = "in_scope" | "out_of_scope" | "insufficient_context";
type Label = "promotion" | "educational" | "unclear";

/* "out_of_scope" / "insufficient_context" / "question" never produce a
   verdict, so they must never render as a passing caution grade. */
type Classification =
  | "education"
  | "mixed"
  | "promotion"
  | "out_of_scope"
  | "insufficient_context"
  | "question";
type CautionLevel = "low" | "medium" | "high" | "not_applicable";

interface Claim {
  quote: string;
  claim_type: string;
  flags: string[];
  reason: string;
}

/* One persuasion signal with the verbatim span that produced it. */
interface RedFlag {
  category: string;
  label: string;
  quote: string;
  note: string;
}

interface VerificationItem {
  label: string;
  status: "present" | "missing" | "cannot_verify";
  url: string;
  note: string;
}

interface AnalyzeResponse {
  scope: Scope;
  label: Label;
  classification: Classification;
  caution_level: CautionLevel;
  caution_score: number;
  /* Auditable: a documented function of the evidence observed, not a
     model logit. Low by design whenever we abstain. */
  confidence: number;
  summary: string;
  claims: Claim[];
  flags: string[];
  flag_labels: string[];
  persuasion_categories: string[];
  red_flags: RedFlag[];
  education_markers: string[];
  what_to_verify: string[];
  /* Answers a "question" without giving investment advice. Empty otherwise. */
  guidance: string[];
  verification: VerificationItem[];
  disclaimer: string;
  rubric_version: string;
  /* The shadow classifier only knows the 3 in-scope labels. Kept in the API
     response for the eval track, but deliberately not rendered: it is
     pre-review synthetic data and showing it "disagreeing" with the verdict
     just tells users our own tool contradicts itself. */
  model?: { label: ModelLabel; confidence: number } | null;
}
type ModelLabel = Exclude<Classification, "out_of_scope" | "question" | "insufficient_context">;

interface IngestUrlResponse {
  transcript: string;
  detected_language: string;
  duration_sec: number;
  model: string;
  /* Which path produced the text. Shown so the user knows whether we read a
     caption track or transcribed the audio themselves. */
  source: "captions" | "media";
  title: string | null;
  truncated: boolean;
  dropped_chars: number;
}

/* ------------------------------------------------------------------ config */

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const MAX_LEN = 8000;
const MIN_LEN = 10;
// Same grievance portal the analyzer links in OFFICIAL_SOURCES["scores"].
const SCORES_URL = "https://scores.sebi.gov.in/";

/* `key` is a dictionary key, not the label: the visible name is translated.
   The bodies stay exactly as written -- they are illustrative *content*, and
   rewriting a promotional sample into Hindi would change what the rubric is
   being demonstrated on. */
const SAMPLES: { key: string; text: string }[] = [
  {
    key: "sample.promotion",
    text: "Guaranteed returns! Double your money in 30 days, 100% safe with no risk. Join our premium Telegram group now. Limited seats, hurry! My student earned 2 lakh profit last month from my secret strategy.",
  },
  {
    key: "sample.education",
    text: "A mutual fund pools money from many investors to buy stocks and bonds. Mutual fund investments are subject to market risks. This video is for educational purposes only and is not investment advice. Please consult a SEBI-registered investment adviser before deciding.",
  },
  {
    key: "sample.mixed",
    text: "Compounding means your returns also earn returns over time, which is why starting early matters. My follower made lakhs using this trick. DM me to join my VIP group, offer ends today!",
  },
  {
    key: "sample.offTopic",
    text: "Just had pizza with friends at the park this afternoon. Football match was great, going to sleep now.",
  },
];

/* Offline fallback so the Day-1 demo never goes blank if the API is down.
   Clearly labelled in the UI as an offline demo response. */
const OFFLINE_DEMO: AnalyzeResponse = {
  scope: "in_scope",
  label: "educational",
  classification: "mixed",
  caution_level: "medium",
  caution_score: 3,
  confidence: 0.42,
  summary:
    "This content explains a financial concept but also promotes a paid group. (Offline demo response. Start the FastAPI service for live analysis.)",
  claims: [
    {
      quote: "Join our group for guaranteed returns",
      claim_type: "return_promise",
      flags: ["unrealistic_returns", "paid_service_cta"],
      reason: "It promises a result and directs viewers to a paid service.",
    },
  ],
  flags: ["unrealistic_returns", "paid_service_cta"],
  flag_labels: [
    "Guaranteed / unrealistic returns",
    "Call to join group / app / paid service",
  ],
  persuasion_categories: ["return_promise", "commercial_cta"],
  red_flags: [
    {
      category: "return_promise",
      label: "Guaranteed or implausible return",
      quote: "Join our group for guaranteed returns",
      note: "It promises a result and directs viewers to a paid service.",
    },
  ],
  education_markers: [],
  what_to_verify: [
    "Ask what annualised return is being promised, in writing. If the answer is a guaranteed figure, that is the finding on its own.",
  ],
  guidance: [],
  verification: [
    {
      label: "SEBI registration",
      status: "cannot_verify",
      url: "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13",
      note: "We cannot check advisor registration from text alone. Search the name on SEBI's official Investment Adviser list.",
    },
    {
      label: "Risk disclosure",
      status: "missing",
      url: "https://investor.sebi.gov.in/",
      note: "No risk disclaimer found. Registered content must follow SEBI's advertisement code (CIR/2023/51).",
    },
    {
      label: "Official circular / notice",
      status: "cannot_verify",
      url: "https://www.sebi.gov.in/legal/circulars/apr-2023/advertisement-code-for-investment-advisers-ia-and-research-analysts-ra-_69798.html",
      note: "If the content cites a circular, verify it on SEBI's official site. Start with the IA/RA advertisement code circular (CIR/2023/51).",
    },
  ],
  disclaimer: "This is an awareness tool, not investment advice.",
  rubric_version: "rubric-v1.5 (offline)",
};

/* Hindi offline demo. Same stable codes, quotes, and URLs as OFFLINE_DEMO;
   only the human-readable prose is translated, mirroring analyzer.py. */
const OFFLINE_DEMO_HI: AnalyzeResponse = {
  ...OFFLINE_DEMO,
  summary:
    "यह सामग्री वित्तीय अवधारणा समझाती है, साथ ही सशुल्क ग्रुप का प्रचार भी करती है।",
  claims: [
    {
      quote: "Join our group for guaranteed returns",
      claim_type: "return_promise",
      flags: ["unrealistic_returns", "paid_service_cta"],
      reason:
        "यह नतीजे का वादा करता है और दर्शकों को सशुल्क सेवा की ओर ले जाता है।",
    },
  ],
  flag_labels: [
    "गारंटीड / अवास्तविक रिटर्न",
    "ग्रुप / ऐप / सशुल्क सेवा में जुड़ने की बात",
  ],
  red_flags: [
    {
      category: "return_promise",
      label: "गारंटीड या अविश्वसनीय रिटर्न",
      quote: "Join our group for guaranteed returns",
      note: "यह नतीजे का वादा करता है और दर्शकों को सशुल्क सेवा की ओर ले जाता है।",
    },
  ],
  what_to_verify: [
    "लिखित में पूछें कि कौन-सा वार्षिक रिटर्न देने का वादा है। अगर जवाब में गारंटीड आँकड़ा है, तो वही अपने आप में निष्कर्ष है।",
  ],
  verification: [
    {
      label: "SEBI पंजीकरण",
      status: "cannot_verify",
      url: "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13",
      note: "टेक्स्ट से सलाहकार पंजीकरण जाँचा नहीं जा सकता। SEBI की आधिकारिक निवेश सलाहकार सूची में नाम खोजें।",
    },
    {
      label: "जोखिम प्रकटीकरण",
      status: "missing",
      url: "https://investor.sebi.gov.in/",
      note: "कोई जोखिम प्रकटीकरण नहीं मिला। पंजीकृत सामग्री को SEBI के विज्ञापन कोड (CIR/2023/51) का पालन करना चाहिए।",
    },
    {
      label: "आधिकारिक परिपत्रिका / सूचना",
      status: "cannot_verify",
      url: "https://www.sebi.gov.in/legal/circulars/apr-2023/advertisement-code-for-investment-advisers-ia-and-research-analysts-ra-_69798.html",
      note: "अगर सामग्री में परिपत्रिका का हवाला है, तो उसे SEBI की आधिकारिक साइट पर जाँचें। IA/RA विज्ञापन कोड परिपत्रिका (CIR/2023/51) से शुरुआत करें।",
    },
  ],
  disclaimer: "यह जागरूकता उपकरण है, निवेश सलाह नहीं।",
  rubric_version: "rubric-v1.5 (ऑफ़लाइन)",
};

/* Both tables below are now dictionary keys, not copy. The English text lives in
   src/i18n.ts beside its Hindi translation, which is the only way to keep the two
   in sync -- splitting them across files is how translations silently rot. */
/* The rubric taxonomy as dictionary keys. Same seven categories the API
   returns in flag_labels; the rail lists them statically so the user can see
   the whole rubric before running anything. */
const RUBRIC_KEYS = [
  "rubric.0",
  "rubric.1",
  "rubric.2",
  "rubric.3",
  "rubric.4",
  "rubric.5",
  "rubric.6",
];

const NEXT_STEP_KEYS: Record<Classification, string[]> = {
  education: ["next.education.0", "next.education.1", "next.education.2"],
  mixed: ["next.mixed.0", "next.mixed.1", "next.mixed.2"],
  promotion: ["next.promotion.0", "next.promotion.1", "next.promotion.2"],
  out_of_scope: ["next.out_of_scope.0", "next.out_of_scope.1", "next.out_of_scope.2"],
  question: ["next.question.0", "next.question.1", "next.question.2"],
  insufficient_context: [
    "next.insufficient_context.0",
    "next.insufficient_context.1",
    "next.insufficient_context.2",
  ],
};

/* ------------------------------------------------------------------ helpers */

function highlightTranscript(text: string, claims: Claim[]): ReactNode {
  const ranges: { start: number; end: number }[] = [];
  for (const c of claims) {
    const idx = text.indexOf(c.quote);
    if (idx >= 0) ranges.push({ start: idx, end: idx + c.quote.length });
    else if (c.quote.length > 60) {
      const anchor = c.quote.slice(0, 60);
      const a = text.indexOf(anchor);
      if (a >= 0) ranges.push({ start: a, end: Math.min(a + c.quote.length, text.length) });
    }
  }
  ranges.sort((a, b) => a.start - b.start);
  const merged = ranges.filter((r, i) => i === 0 || r.start >= ranges[i - 1].end);
  if (merged.length === 0) return <p className="transcript-text">{text}</p>;

  const parts: ReactNode[] = [];
  let cursor = 0;
  merged.forEach((r, i) => {
    if (r.start > cursor) parts.push(<span key={`t${i}`}>{text.slice(cursor, r.start)}</span>);
    parts.push(
      <mark key={`m${i}`} className="hl">
        {text.slice(r.start, r.end)}
      </mark>
    );
    cursor = r.end;
  });
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <p className="transcript-text">{parts}</p>;
}

function riseDelay(ms: number): CSSProperties {
  return { "--rd": `${ms}ms` } as CSSProperties;
}

/* ------------------------------------------------------------------ app */

export default function App() {
  const { t, theme, toggleTheme, lang, setLang } = usePrefs();
  const [input, setInput] = useState("");
  const [audioName, setAudioName] = useState<string | null>(null);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioNote, setAudioNote] = useState<string | null>(null);
  const [shotBusy, setShotBusy] = useState(false);
  const [shotNote, setShotNote] = useState<string | null>(null);
  const [urlValue, setUrlValue] = useState("");
  const [urlBusy, setUrlBusy] = useState(false);
  const [urlNote, setUrlNote] = useState<string | null>(null);
  const [listenBusy, setListenBusy] = useState(false);
  const [langHint, setLangHint] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [sourceText, setSourceText] = useState("");
  const [offline, setOffline] = useState(false);
  const [copied, setCopied] = useState(false);

  const remaining = MAX_LEN - input.length;
  const tooShort = input.trim().length < MIN_LEN;
  // An empty box is not a warning, so it must not wear the warning colour --
  // "0/8000 min 10" in alert orange on first load reads as something wrong.
  // Only start warning once there is actually something there.
  const warnShort = tooShort && input.trim().length > 0;

  const verdictMeta = useMemo(() => {
    if (!result) return null;
    const c = result.classification;
    return { title: t(`verdict.${c}.title`), blurb: t(`verdict.${c}.blurb`) };
  }, [result, t]);

  /* Stable analyzer flag codes get display names here. Unknown codes fall back
     to the readable code, so a future rubric addition can never blank a pill. */
  const flagLabel = (f: string) => {
    const key = `flag.${f}`;
    const v = t(key);
    return v === key ? f.replace(/_/g, " ") : v;
  };

  function switchLang(next: Lang) {
    // The API payload is generated in the request language, so a result
    // analyzed in English keeps English prose after a toggle. Re-run the
    // same input when a result is on screen; quotes stay verbatim either way.
    setLang(next);
    if (next !== lang && result && !loading && input.trim().length >= MIN_LEN) {
      void handleAnalyze(next);
    }
  }

  async function handleAnalyze(overrideLang?: Lang) {
    // A language switch re-runs analysis so the stored payload is regenerated
    // in the new language. The override is needed because setLang() hasn't
    // re-rendered yet when the toggle calls this -- the closure still holds
    // the old lang, so the request would go out (and the offline fallback
    // would render) in the previous language.
    const activeLang = overrideLang ?? lang;
    const tt = overrideLang ? makeT(overrideLang) : t;
    const text = input.trim();
    if (text.length < MIN_LEN) {
      setError(tt("input.tooShort", { n: MIN_LEN }));
      return;
    }
    setLoading(true);
    setError(null);
    setCopied(false);
    try {
      const res = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language_hint: "auto", ui_language: activeLang }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const detail = body?.detail
          ? Array.isArray(body.detail)
            ? body.detail.map((d: { msg?: string }) => d.msg).join("; ")
            : String(body.detail)
          : `Server returned ${res.status}`;
        throw new Error(detail);
      }
      const data = (await res.json()) as AnalyzeResponse;
      setResult(data);
      setOffline(false);
    } catch {
      const tailored: AnalyzeResponse = {
        ...(activeLang === "hi" ? OFFLINE_DEMO_HI : OFFLINE_DEMO),
        summary: tt("offline.summary", { n: text.length }),
        rubric_version: tt("offline.rubric"),
      };
      setResult(tailored);
      setOffline(true);
    } finally {
      setSourceText(text);
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!result) return;
    const cautionKey =
      result.caution_level === "not_applicable"
        ? "meter.na"
        : `meter.level.${result.caution_level}`;
    const lines = [
      `${t(`verdict.${result.classification}.title`)} (${t(cautionKey)})`,
      result.summary,
      ...result.claims.map(
        (c) =>
          `- "${c.quote}" [${c.flags.map((f) => flagLabel(f)).join(", ")}]: ${c.reason}`
      ),
      result.disclaimer,
    ].join("\n");
    navigator.clipboard?.writeText(lines).then(
      () => setCopied(true),
      () => setCopied(false)
    );
  }

  function reset() {
    setResult(null);
    setError(null);
    setOffline(false);
    setCopied(false);
    setUrlNote(null);
  }

  /* Audio, screenshots and pasted links all dump text into the same textarea,
     and a 3-minute clip can produce more than /api/analyze accepts. The
     textarea's maxLength would clip that silently, so the user would get a
     confident verdict resting on half the reel with no idea. Clip deliberately
     and say so instead. */
  function clipForAnalyze(text: string, serverDropped = 0) {
    const over = Math.max(0, text.length - MAX_LEN);
    const dropped = over + serverDropped;
    return {
      text: over ? text.slice(0, MAX_LEN) : text,
      dropped,
      warning: dropped
        ? ` That was longer than the ${MAX_LEN.toLocaleString()}-character limit, so only the first ${MAX_LEN.toLocaleString()} characters were kept (${dropped.toLocaleString()} dropped). The verdict covers that part only — split longer clips if you need the rest.`
        : "",
    };
  }

  async function handleShot(file: File | undefined) {
    if (!file) return;
    setShotNote(null);
    setError(null);
    if (file.size > 10 * 1024 * 1024) {
      setError(t("img.tooBig"));
      return;
    }
    setShotBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/api/ocr`, { method: "POST", body: form });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Could not read that image (${res.status})`);
      const clip = clipForAnalyze(body.text);
      setInput(clip.text);
      setShotNote(
        `Screenshot text extracted (${body.blocks.length} regions). Check it, edit if needed, then analyze.${clip.warning}`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("img.err"));
    } finally {
      setShotBusy(false);
    }
  }

  async function handleAudio(file: File | undefined) {
    if (!file) return;
    setAudioName(file.name);
    setAudioNote(null);
    setError(null);
    if (file.size > 25 * 1024 * 1024) {
      setError(t("audio.tooBig"));
      return;
    }
    setAudioBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/api/transcribe?language_hint=${langHint}`, {
        method: "POST",
        body: form,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Transcription failed (${res.status})`);
      const clip = clipForAnalyze(body.transcript);
      setInput(clip.text);
      setAudioNote(
        `Transcript ready (${body.duration_sec}s, detected: ${body.detected_language}). Check it, edit if needed, then analyze.${clip.warning}`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("audio.err"));
    } finally {
      setAudioBusy(false);
    }
  }

  /* Tab capture lands here as a webm/opus blob. It goes to the same
     /api/transcribe endpoint as a file upload, so ffmpeg, hosted STT and the
     language routing are all shared - no separate path to keep working.
     30s of Opus is ~120 KB, far inside the 25 MB limit. */
  async function handleListenClip(result: TabCaptureResult) {
    setListenBusy(true);
    setAudioNote(null);
    setError(null);
    const secs = (result.durationMs / 1000).toFixed(1);
    try {
      const form = new FormData();
      // The filename carries the extension the API's allowlist checks. The blob
      // itself is audio/webm;codecs=opus, which ffmpeg decodes directly.
      form.append("file", result.blob, "tab-capture.webm");
      const res = await fetch(`${API_URL}/api/transcribe?language_hint=${langHint}`, {
        method: "POST",
        body: form,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Transcription failed (${res.status})`);
      const clip = clipForAnalyze(body.transcript);
      setInput(clip.text);
      const stopped =
        result.reason === "user"
          ? "stopped early"
          : result.reason === "share_ended"
            ? "ended when you stopped sharing"
            : "hit the timer";
      setAudioNote(
        `Transcript from the tab (${secs}s captured, ${stopped}; detected: ${body.detected_language}). Tab audio is noisy — check it, fix anything wrong, then analyze.${clip.warning}`
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t("tab.errGeneric")
      );
    } finally {
      setListenBusy(false);
    }
  }

  async function handleUrl() {
    const url = urlValue.trim();
    if (!url || urlBusy) return;
    setUrlNote(null);
    setError(null);
    setAudioNote(null);
    setUrlBusy(true);
    try {
      const res = await fetch(`${API_URL}/api/ingest-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, language_hint: langHint }),
      });
      const body: IngestUrlResponse | { detail?: string } | null = await res
        .json()
        .catch(() => null);
      if (!res.ok) {
        throw new Error(
          (body as { detail?: string })?.detail ?? `Could not read that link (${res.status})`
        );
      }
      const ok = body as IngestUrlResponse;
      const clip = clipForAnalyze(ok.transcript, ok.dropped_chars);
      setInput(clip.text);
      // Say which path ran. Captions come back in seconds; audio transcription
      // is CPU-bound and slow, and the user should know which one they waited for.
      const how =
        ok.source === "captions"
          ? "Read from the post's own captions"
          : "No captions on that post, so we transcribed the audio";
      const dur = ok.duration_sec ? `, ${ok.duration_sec}s` : "";
      setUrlNote(
        `Transcript ready from ${ok.title ? `"${ok.title}"` : "that link"} (${how}, detected: ${ok.detected_language}${dur}). Check it, edit if needed, then analyze.${clip.warning}`
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t("link.errGeneric")
      );
    } finally {
      setUrlBusy(false);
    }
  }

  return (
    <div className="page">
      <Backdrop />
      <ScrollProgress />

      <header className="topbar rise">
        <Logo />
        <span className="track-badge">{t("brand.track")}</span>
        <div className="prefs">
          <button
            type="button"
            className="icon-btn"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? t("nav.theme") : t("nav.themeDark")}
            title={theme === "dark" ? t("nav.theme") : t("nav.themeDark")}
          >
            {theme === "dark" ? (
              <Sun size={17} weight="bold" aria-hidden="true" />
            ) : (
              <Moon size={17} weight="bold" aria-hidden="true" />
            )}
          </button>
          <div className="lang-switch" role="group" aria-label={t("nav.lang")}>
            <Globe size={15} weight="bold" aria-hidden="true" className="lang-globe" />
            <button
              type="button"
              className={lang === "en" ? "lang-opt is-on" : "lang-opt"}
              onClick={() => switchLang("en")}
              aria-pressed={lang === "en"}
              lang="en"
            >
              EN
            </button>
            <button
              type="button"
              className={lang === "hi" ? "lang-opt is-on" : "lang-opt"}
              onClick={() => switchLang("hi")}
              aria-pressed={lang === "hi"}
              lang="hi"
            >
              हिं
            </button>
          </div>
        </div>
      </header>

      <div className="notice rise" style={riseDelay(60)} role="note">
        <strong>{t("notice.1")}</strong> {t("notice.2")}
      </div>

      {!result ? (
        <main className="layout">
          <div className="hero-col">
            <div className="hero rise" style={riseDelay(100)}>
              <span className="hero-pill">{t("hero.pill")}</span>
              <h1 className="hero-title">
                <SplitText text={t("hero.title1")} stagger={16} /> <br />
                <em className="accent">
                  <SplitText text={t("hero.title2")} baseDelay={280} stagger={16} />
                </em>
              </h1>
              <p className="lede">
                {t("hero.lede")}
              </p>
            </div>

            <Card className="input-card rise" style={riseDelay(180)}>
              <div className="sample-row" aria-label={t("input.samplesAria")}>
                <span className="sample-label">{t("input.tryLabel")}</span>
                {SAMPLES.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    className="chip-btn"
                    onClick={() => {
                      setInput(s.text);
                      setError(null);
                    }}
                  >
                    {t(s.key)}
                  </button>
                ))}
              </div>

              <label className="field-label" htmlFor="content">
                {t("input.contentLabel")}
              </label>
              <textarea
                id="content"
                className="textarea"
                placeholder={t("input.placeholder")}
                value={input}
                maxLength={MAX_LEN}
                rows={7}
                onChange={(e) => setInput(e.target.value)}
              />
              <div className="meta-row">
                <span className={warnShort ? "count warn" : "count"}>
                  {input.trim().length}/{MAX_LEN} {t("input.countMin")} {MIN_LEN}
                </span>
                <span className="count">{remaining} {t("input.countLeft")}</span>
              </div>

              <div className="listen-wrap">
                <ListenPanel onClip={(r) => void handleListenClip(r)} busy={listenBusy} />
              </div>

              <div className="audio-row">
                <div className={`link-box ${urlBusy ? "busy" : ""}`}>
                  <span className="audio-icon" aria-hidden="true">
                    <LinkSimple size={18} weight="bold" />
                  </span>
                  <div className="link-fields">
                    <input
                      id="srcurl"
                      className="link-input"
                      type="url"
                      inputMode="url"
                      autoComplete="off"
                      spellCheck={false}
                      placeholder={t("link.placeholder")}
                      aria-label={t("link.aria")}
                      value={urlValue}
                      disabled={urlBusy}
                      onChange={(e) => setUrlValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void handleUrl();
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="link-go"
                      onClick={() => void handleUrl()}
                      disabled={urlBusy || !urlValue.trim()}
                    >
                      {urlBusy ? t("link.busy") : t("link.go")}
                    </button>
                  </div>
                </div>
                <p className="hint-row link-hint">
                  {t("link.hint")}
                </p>
                {urlNote && <p className="audio-note">{urlNote}</p>}
              </div>

              <div className="audio-row">
                <label className={`audio-box ${audioBusy ? "busy" : ""}`} title={t("audio.title")}>
                  <input
                    type="file"
                    accept="audio/*,video/*"
                    hidden
                    disabled={audioBusy}
                    onChange={(e) => void handleAudio(e.target.files?.[0])}
                  />
                  <span className="audio-icon" aria-hidden="true">
                    <Microphone size={18} weight="bold" />
                  </span>
                  <span className="audio-text">
                    <strong>
                      {audioBusy ? t("audio.busy") : audioName ?? t("audio.attach")}
                    </strong>
                    <small>{t("audio.hintFormats")}</small>
                  </span>
                  <span className="soon">{t("audio.onDevice")}</span>
                </label>
                <div className="hint-row">
                  <label htmlFor="langhint">{t("audio.langLabel")}</label>
                  <select
                    id="langhint"
                    value={langHint}
                    onChange={(e) => setLangHint(e.target.value)}
                    disabled={audioBusy}
                  >
                    <option value="auto">{t("audio.langAuto")}</option>
                    <option value="hi">{t("audio.langHi")}</option>
                    <option value="en">{t("audio.langEn")}</option>
                  </select>
                </div>
                {audioNote && <p className="audio-note">{audioNote}</p>}
              </div>

              <div className="audio-row">
                <label className={`audio-box ${shotBusy ? "busy" : ""}`} title={t("shot.title")}>
                  <input
                    type="file"
                    accept="image/*"
                    hidden
                    disabled={shotBusy}
                    onChange={(e) => void handleShot(e.target.files?.[0])}
                  />
                  <span className="audio-icon" aria-hidden="true">
                    <ImageIcon size={18} weight="bold" />
                  </span>
                  <span className="audio-text">
                    <strong>
                      {shotBusy ? t("shot.busy") : t("shot.attach")}
                    </strong>
                    <small>{t("shot.hint")}</small>
                  </span>
                  <span className="soon">{t("audio.onDevice")}</span>
                </label>
                {shotNote && <p className="audio-note">{shotNote}</p>}
              </div>

              {error && (
                <div className="error" role="alert">
                  {error}
                </div>
              )}

              <Magnet>
                <button
                  className="primary btn-shimmer"
                  onClick={() => void handleAnalyze()}
                  disabled={loading || tooShort}
                >
                  {loading ? (
                    // Only the three dot spans may be <span>: the CSS blinks
                    // every span inside .loading-dots and staggers nth-child(2/3).
                    // The word itself must stay a bare text node.
                    <span className="loading-dots">
                      {t("input.analyzing")}
                      <span>.</span>
                      <span>.</span>
                      <span>.</span>
                    </span>
                  ) : (
                    t("input.analyze")
                  )}
                </button>
              </Magnet>
              <p className="privacy">
                {t("input.privacy.a")} <em>{t("input.privacy.em")}</em>
                {t("input.privacy.b")}
              </p>
            </Card>
          </div>

          <aside className="side">
            <Card className="rise" style={riseDelay(240)}>
              <Card.Header>
                <Card.Title>{t("rail.how.title")}</Card.Title>
                <Card.Description>{t("rail.how.desc")}</Card.Description>
              </Card.Header>
              <Card.Content>
                <ol className="steps">
                  <li>
                    <span className="step-n">1</span>
                    <div>
                      <strong>{t("rail.step1.t")}</strong>
                      <span>{t("rail.step1.d")}</span>
                    </div>
                  </li>
                  <li>
                    <span className="step-n">2</span>
                    <div>
                      <strong>{t("rail.step2.t")}</strong>
                      <span>{t("rail.step2.d")}</span>
                    </div>
                  </li>
                  <li>
                    <span className="step-n">3</span>
                    <div>
                      <strong>{t("rail.step3.t")}</strong>
                      <span>{t("rail.step3.d")}</span>
                    </div>
                  </li>
                </ol>
              </Card.Content>
            </Card>

            <Card className="rise" style={riseDelay(300)}>
              <Card.Header>
                <Card.Title>Rubric v1.3</Card.Title>
                <Card.Description>{t("rail.rubric.desc")}</Card.Description>
              </Card.Header>
              <Card.Content>
                <ul className="rubric">
                  {RUBRIC_KEYS.map((k) => (
                    <li key={k}>{t(k)}</li>
                  ))}
                </ul>
                <p className="fine">{t("rail.weights")}</p>
              </Card.Content>
            </Card>
          </aside>
        </main>
      ) : (
        <main className="layout result-layout">
          <Card
            key={`${result.classification}-${result.caution_score}`}
            className={`verdict verdict-${result.classification} rise`}
          >
            <Card.Content>
              <div className="verdict-top">
                <div className="verdict-head">
                  <div className="eyebrow">
                    {t("verdict.result")} {result.rubric_version}
                    {offline && <span className="offline-pill">{t("verdict.offline")}</span>}
                  </div>
                  <h1 className="verdict-title">
                    <SplitText text={verdictMeta?.title ?? ""} stagger={22} />
                  </h1>
                  <p className="lede">{verdictMeta?.blurb}</p>
                </div>
                {/* No score exists for text we never rated. Rendering "0 / 10" would
                    read as a passing caution grade, which is wrong for
                    out-of-scope text, a fragment, and a question alike. */}
                {result.classification !== "out_of_scope" &&
                    result.classification !== "question" &&
                    result.classification !== "insufficient_context" && (
                      <div className="meter-wrap">
                        <Meter
                          value={result.caution_score}
                          max={10}
                          level={result.caution_level as Exclude<CautionLevel, "not_applicable">}
                          label={t("verdict.caution")}
                          levelText={t(`meter.level.${result.caution_level}`)}
                          scale={[t("meter.scale.low"), t("meter.scale.medium"), t("meter.scale.high")]}
                        />
                      </div>
                    )}
                {result.scope === "in_scope" && (
                  <div className="conf-wrap" aria-label={t("verdict.confidence")}>
                    <span className="conf-label">{t("verdict.confidence")}</span>
                    <span className="conf-track" role="img" aria-label={t("verdict.confidenceAria", { n: Math.round(result.confidence * 100) })}>
                      <span
                        className={`conf-fill conf-${result.confidence < 0.6 ? "low" : "high"}`}
                        style={{ width: `${Math.round(result.confidence * 100)}%` }}
                      />
                    </span>
                    <span className="conf-num">{result.confidence.toFixed(2)}</span>
                  </div>
                )}
              </div>

              <p className="summary">{result.summary}</p>

              {result.guidance.length > 0 && (
                <ul className="guidance" aria-label="What we can tell you">
                  {result.guidance.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              )}

              {result.flag_labels.length > 0 && (
                <div className="flag-chips" aria-label={t("verdict.signals")}>
                  {result.flag_labels.map((f) => (
                    <span key={f} className="flag-chip">
                      <Flag size={13} weight="bold" aria-hidden="true" /> {f}
                    </span>
                  ))}
                </div>
              )}

              <div className="actions">
                <Magnet strength={10} className="actions-magnet">
                  <button className="primary btn-shimmer" onClick={reset}>
                    {t("verdict.another")}
                  </button>
                </Magnet>
                <button className="ghost" onClick={handleCopy}>
                  {copied ? <Check size={15} weight="bold" aria-hidden="true" /> : <Copy size={15} weight="bold" aria-hidden="true" />}{" "}
                  {copied ? t("verdict.copied") : t("verdict.copy")}
                </button>
                {/* Promotion is the only verdict that can warrant a fraud report.
                    This never files anything itself; it hands the user to SEBI
                    SCORES, the same portal the analyzer cites. */}
                {result.classification === "promotion" && (
                  <a
                    className="ghost report"
                    href={SCORES_URL}
                    target="_blank"
                    rel="noreferrer"
                    title={t("report.title")}
                  >
                    <ArrowSquareOut size={15} weight="bold" aria-hidden="true" />{" "}
                    {t("report.cta")}
                  </a>
                )}
              </div>
            </Card.Content>
          </Card>

          <Card className="rise" style={riseDelay(90)}>
            <Card.Header>
              <Card.Title>{t("panel.source.title")}</Card.Title>
              <Card.Description>
                {result.claims.length === 0
                  ? t("panel.source.none")
                  : t("panel.source.count", { n: result.claims.length, s: result.claims.length > 1 ? "s" : "" })}
              </Card.Description>
            </Card.Header>
            <Card.Content>{highlightTranscript(sourceText, result.claims)}</Card.Content>
          </Card>

          <Card className="rise" style={riseDelay(140)}>
            <Card.Header>
              <Card.Title>{t("panel.claims.title", { n: result.claims.length })}</Card.Title>
              <Card.Description>{t("panel.claims.desc")}</Card.Description>
            </Card.Header>
            <Card.Content>
              {result.claims.length === 0 ? (
                <p className="lede">
                  {result.classification === "out_of_scope"
                    ? t("panel.claims.outOfScope")
                    : result.classification === "insufficient_context"
                      ? t("panel.claims.insufficient")
                      : t("panel.claims.clean")}
                </p>
              ) : (
                <ul className="claims">
                  {result.claims.map((c, i) => (
                    <li key={i} className="claim">
                      <blockquote>&ldquo;{c.quote}&rdquo;</blockquote>
                      <div className="claim-meta">
                        <span className="type-pill">
                          {t(`claimType.${c.claim_type}`)}
                        </span>
                        {c.flags.map((f) => (
                          <span key={f} className="mini-flag">
                            {flagLabel(f)}
                          </span>
                        ))}
                      </div>
                      <p className="reason">{c.reason}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Card.Content>
          </Card>

          <Card className="guidance-card rise" style={riseDelay(190)}>
            <Card.Header>
              <Card.Title>{t("panel.guidance.title")}</Card.Title>
              <Card.Description>{t("panel.guidance.desc")}</Card.Description>
            </Card.Header>
            <Card.Content>
              {/* Two independent lists, so they sit side by side rather than
                  stacking into one tall narrow column. auto-fit collapses the
                  spare track when there is no per-text checklist to show. */}
              <div className="guidance-cols">
                <ul className="next">
                  {NEXT_STEP_KEYS[result.classification].map((k) => (
                    <li key={k}>{t(k)}</li>
                  ))}
                </ul>

                {result.what_to_verify.length > 0 && (
                  <section>
                    <h3 className="sub-h">{t("panel.guidance.verifyText")}</h3>
                    <ul className="next">
                      {result.what_to_verify.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>

              <h3 className="sub-h">{t("panel.guidance.official")}</h3>
              <ul className="verify">
                {result.verification.map((v) => (
                  <li key={v.label} className="v-row">
                    <div>
                      <div className="v-head">
                        <strong>{v.label}</strong>
                        <span className={`status status-${v.status}`}>
                          {t(`status.${v.status}`)}
                        </span>
                      </div>
                      <p>{v.note}</p>
                    </div>
                    <a href={v.url} target="_blank" rel="noreferrer" className="v-link">
                      {t("panel.official.link")} <ArrowSquareOut size={14} weight="bold" aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ul>
            </Card.Content>
          </Card>

          <Card className="privacy-box rise" style={riseDelay(240)}>
            <Card.Header>
              <Card.Title>{t("panel.privacy.title")}</Card.Title>
            </Card.Header>
            <Card.Content>
              <p>{t("panel.privacy.body")}</p>
              <p className="disclaimer-line">{result.disclaimer}</p>
            </Card.Content>
          </Card>
        </main>
      )}

      <footer className="footer">
        <span>{t("footer.built")}</span>
        <span>{t("footer.disclaimer")}</span>
      </footer>
    </div>
  );
}
