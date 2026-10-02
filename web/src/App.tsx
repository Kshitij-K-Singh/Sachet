import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { ArrowSquareOut, Check, Copy, Flag, Image as ImageIcon, Microphone } from "@phosphor-icons/react";
import Backdrop from "./bits/Backdrop";
import Magnet from "./bits/Magnet";
import ScrollProgress from "./bits/ScrollProgress";
import SplitText from "./bits/SplitText";
import Card from "./ui/Card";
import Meter from "./ui/Meter";
import "./App.css";

/* ------------------------------------------------------------------ types
   Mirrors api/main.py AnalyzeResponse. Keep in sync; contract v1. */

type Classification = "education" | "mixed" | "promotion";
type CautionLevel = "low" | "medium" | "high";

interface Claim {
  quote: string;
  claim_type: string;
  flags: string[];
  reason: string;
}

interface VerificationItem {
  label: string;
  status: "present" | "missing" | "cannot_verify";
  url: string;
  note: string;
}

interface AnalyzeResponse {
  classification: Classification;
  caution_level: CautionLevel;
  caution_score: number;
  summary: string;
  claims: Claim[];
  flags: string[];
  flag_labels: string[];
  verification: VerificationItem[];
  disclaimer: string;
  rubric_version: string;
  model?: { label: Classification; confidence: number } | null;
}

/* ------------------------------------------------------------------ config */

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const MAX_LEN = 8000;
const MIN_LEN = 10;

const SAMPLES: { name: string; text: string }[] = [
  {
    name: "Promotional reel",
    text: "Guaranteed returns! Double your money in 30 days, 100% safe with no risk. Join our premium Telegram group now. Limited seats, hurry! My student earned 2 lakh profit last month from my secret strategy.",
  },
  {
    name: "Genuine lesson",
    text: "A mutual fund pools money from many investors to buy stocks and bonds. Mutual fund investments are subject to market risks. This video is for educational purposes only and is not investment advice. Please consult a SEBI-registered investment adviser before deciding.",
  },
  {
    name: "Mixed post",
    text: "Compounding means your returns also earn returns over time, which is why starting early matters. My follower made lakhs using this trick. DM me to join my VIP group, offer ends today!",
  },
];

/* Offline fallback so the Day-1 demo never goes blank if the API is down.
   Clearly labelled in the UI as an offline demo response. */
const OFFLINE_DEMO: AnalyzeResponse = {
  classification: "mixed",
  caution_level: "medium",
  caution_score: 3,
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
  rubric_version: "rubric-v1.1 (offline)",
};

const CLAIM_TYPE_LABELS: Record<string, string> = {
  return_promise: "Return promise",
  risk_denial: "Risk denial",
  authority: "Authority claim",
  urgency: "Urgency",
  testimonial: "Testimonial",
  product_pitch: "Product pitch",
  neutral_fact: "Neutral fact",
};

const NEXT_STEPS: Record<Classification, string[]> = {
  education: [
    "No promotional pattern found, but still verify any names or figures independently.",
    "Check advisor names on SEBI's official intermediary list before acting.",
    "Remember: even good education is not personal investment advice.",
  ],
  mixed: [
    "Separate the lesson from the sales pitch. Learn the concept, ignore the invite.",
    "Do not join paid groups based on profit screenshots alone.",
    "Verify any SEBI/NSDL notice cited here on the official circulars page.",
  ],
  promotion: [
    "Treat guaranteed-return promises as a red flag and pause before acting.",
    "Never pay or share personal details with groups promising assured profits.",
    "You can report suspected fraud on SEBI SCORES: scores.sebi.gov.in.",
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
  const [input, setInput] = useState("");
  const [audioName, setAudioName] = useState<string | null>(null);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioNote, setAudioNote] = useState<string | null>(null);
  const [shotBusy, setShotBusy] = useState(false);
  const [shotNote, setShotNote] = useState<string | null>(null);
  const [langHint, setLangHint] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [sourceText, setSourceText] = useState("");
  const [offline, setOffline] = useState(false);
  const [copied, setCopied] = useState(false);

  const remaining = MAX_LEN - input.length;
  const tooShort = input.trim().length < MIN_LEN;

  const verdictMeta = useMemo(() => {
    if (!result) return null;
    const map: Record<Classification, { title: string; blurb: string }> = {
      education: {
        title: "Looks educational",
        blurb: "Explains a concept without sales pressure.",
      },
      mixed: {
        title: "Mixed: lesson plus sales pitch",
        blurb: "Teaches something, but also pushes you to act or pay.",
      },
      promotion: {
        title: "Looks promotional",
        blurb: "Built to sell, not to teach. Treat its claims with skepticism.",
      },
    };
    return map[result.classification];
  }, [result]);

  async function handleAnalyze() {
    const text = input.trim();
    if (text.length < MIN_LEN) {
      setError(`Please paste at least ${MIN_LEN} characters so there is something to check.`);
      return;
    }
    setLoading(true);
    setError(null);
    setCopied(false);
    try {
      const res = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language_hint: "auto" }),
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
        ...OFFLINE_DEMO,
        summary: `This content explains a financial concept but also promotes a paid group. (Offline demo response. Start the API at localhost:8000 for live rubric analysis of your ${text.length} characters.)`,
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
    const lines = [
      `Sachet result (${result.classification}, caution: ${result.caution_level})`,
      result.summary,
      ...result.claims.map((c) => `- "${c.quote}" [${c.flags.join(", ")}]: ${c.reason}`),
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
  }

  async function handleShot(file: File | undefined) {
    if (!file) return;
    setShotNote(null);
    setError(null);
    if (file.size > 10 * 1024 * 1024) {
      setError("That image is over 10 MB. Compress it and retry.");
      return;
    }
    setShotBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/api/ocr`, { method: "POST", body: form });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Could not read that image (${res.status})`);
      setInput(body.text);
      setShotNote(
        `Screenshot text extracted (${body.blocks.length} regions). Check it, edit if needed, then analyze.`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that image. You can still paste text.");
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
      setError("That file is over 25 MB. Trim it under 3 minutes and retry.");
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
      setInput(body.transcript);
      setAudioNote(
        `Transcript ready (${body.duration_sec}s, detected: ${body.detected_language}). Check it, edit if needed, then analyze.`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transcription failed. You can still paste text.");
    } finally {
      setAudioBusy(false);
    }
  }

  return (
    <div className="page">
      <Backdrop />
      <ScrollProgress />

      <header className="topbar rise">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            स
          </span>
          <div>
            <div className="brand-name">SACHET</div>
            <div className="brand-sub">Promotion vs education analyzer</div>
          </div>
        </div>
        <span className="track-badge">TRACK E</span>
      </header>

      <div className="notice rise" style={riseDelay(60)} role="note">
        <strong>Awareness tool, not investment advice.</strong> We never say whether a
        stock is good or bad. Pasted text is analyzed in memory and never stored.
      </div>

      {!result ? (
        <main className="layout">
          <div className="hero-col">
            <div className="hero rise" style={riseDelay(100)}>
              <span className="hero-pill">SANGYAN 2026</span>
              <h1 className="hero-title">
                <SplitText text="Does it teach," stagger={16} /> <br />
                <em className="accent">
                  <SplitText text="or does it sell?" baseDelay={280} stagger={16} />
                </em>
              </h1>
              <p className="lede">
                Paste a reel caption or message forward. We flag the exact claims and
                rate it: teaches, sells, or both.
              </p>
            </div>

            <Card className="input-card rise" style={riseDelay(180)}>
              <div className="sample-row" aria-label="Try a sample">
                <span className="sample-label">Try:</span>
                {SAMPLES.map((s) => (
                  <button
                    key={s.name}
                    type="button"
                    className="chip-btn"
                    onClick={() => {
                      setInput(s.text);
                      setError(null);
                    }}
                  >
                    {s.name}
                  </button>
                ))}
              </div>

              <label className="field-label" htmlFor="content">
                Content to analyze
              </label>
              <textarea
                id="content"
                className="textarea"
                placeholder="Example: Guaranteed returns! Double your money in 30 days. Join our premium group."
                value={input}
                maxLength={MAX_LEN}
                rows={7}
                onChange={(e) => setInput(e.target.value)}
              />
              <div className="meta-row">
                <span className={tooShort ? "count warn" : "count"}>
                  {input.trim().length}/{MAX_LEN} min {MIN_LEN}
                </span>
                <span className="count">{remaining} left</span>
              </div>

              <div className="audio-row">
                <label className={`audio-box ${audioBusy ? "busy" : ""}`} title="Transcribed on-device with Whisper.cpp">
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
                      {audioBusy ? "Transcribing on-device…" : audioName ?? "Attach a short audio or video clip"}
                    </strong>
                    <small>MP3, WAV, MP4 up to 3 min. Transcript lands in the box above.</small>
                  </span>
                  <span className="soon">ON-DEVICE</span>
                </label>
                <div className="hint-row">
                  <label htmlFor="langhint">Clip language:</label>
                  <select
                    id="langhint"
                    value={langHint}
                    onChange={(e) => setLangHint(e.target.value)}
                    disabled={audioBusy}
                  >
                    <option value="auto">Auto</option>
                    <option value="hi">Hindi</option>
                    <option value="en">English</option>
                  </select>
                </div>
                {audioNote && <p className="audio-note">{audioNote}</p>}
              </div>

              <div className="audio-row">
                <label className={`audio-box ${shotBusy ? "busy" : ""}`} title="Screenshot text extracted on-device with EasyOCR">
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
                      {shotBusy ? "Reading screenshot…" : "Attach a screenshot"}
                    </strong>
                    <small>JPG, PNG, WebP up to 10 MB. Hindi and English text.</small>
                  </span>
                  <span className="soon">ON-DEVICE</span>
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
                  onClick={handleAnalyze}
                  disabled={loading || tooShort}
                >
                  {loading ? (
                    <span className="loading-dots">
                      Analyzing<span>.</span>
                      <span>.</span>
                      <span>.</span>
                    </span>
                  ) : (
                    "Analyze content"
                  )}
                </button>
              </Magnet>
              <p className="privacy">
                Private by design: no accounts, no history, uploads discarded. Results
                always show uncertainty: <em>cannot verify</em>, never <em>false</em>.
              </p>
            </Card>
          </div>

          <aside className="side">
            <Card className="rise" style={riseDelay(240)}>
              <Card.Header>
                <Card.Title>How it works</Card.Title>
                <Card.Description>Three steps, every time.</Card.Description>
              </Card.Header>
              <Card.Content>
                <ol className="steps">
                  <li>
                    <span className="step-n">1</span>
                    <div>
                      <strong>Extract claims</strong>
                      <span>Exact quotes only. Nothing invented.</span>
                    </div>
                  </li>
                  <li>
                    <span className="step-n">2</span>
                    <div>
                      <strong>Apply the fixed rubric</strong>
                      <span>7 flags, each with a plain-language reason.</span>
                    </div>
                  </li>
                  <li>
                    <span className="step-n">3</span>
                    <div>
                      <strong>Verdict plus caution</strong>
                      <span>Education, Mixed, or Promotion, with Low to High caution.</span>
                    </div>
                  </li>
                </ol>
              </Card.Content>
            </Card>

            <Card className="rise" style={riseDelay(300)}>
              <Card.Header>
                <Card.Title>Rubric v1.1</Card.Title>
                <Card.Description>Fixed taxonomy, sourced from SEBI documents. The model only applies it.</Card.Description>
              </Card.Header>
              <Card.Content>
                <ul className="rubric">
                  <li>Guaranteed or unrealistic returns</li>
                  <li>No-risk or safe language</li>
                  <li>Missing risk disclosure</li>
                  <li>Urgency or scarcity pressure</li>
                  <li>Fake or unverifiable authority</li>
                  <li>Testimonial used as evidence</li>
                  <li>Call to join group, app, or paid service</li>
                </ul>
                <p className="fine">
                  Weights: returns x3; risk, authority, paid-CTA x2; rest x1.
                  Score 0-1 is Low, 2-4 Medium, 5+ High.
                </p>
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
                    RESULT {result.rubric_version}
                    {offline && <span className="offline-pill">OFFLINE DEMO</span>}
                  </div>
                  <h1 className="verdict-title">
                    <SplitText text={verdictMeta?.title ?? ""} stagger={22} />
                  </h1>
                  <p className="lede">{verdictMeta?.blurb}</p>
                </div>
                <div className="meter-wrap">
                  <Meter
                    value={result.caution_score}
                    max={10}
                    level={result.caution_level}
                    label="Caution"
                  />
                </div>
              </div>

              <p className="summary">{result.summary}</p>

              {result.flag_labels.length > 0 && (
                <div className="flag-chips" aria-label="Detected patterns">
                  {result.flag_labels.map((f) => (
                    <span key={f} className="flag-chip">
                      <Flag size={13} weight="bold" aria-hidden="true" /> {f}
                    </span>
                  ))}
                </div>
              )}

              {result.model && (
                <p className="model-line" aria-label="Model second opinion">
                  Model second opinion: <strong>{result.model.label}</strong> ({result.model.confidence.toFixed(2)})
                  {" · "}{result.model.label === result.classification ? "agrees" : "disagrees"}
                  {" · "}experimental, pre-review data
                </p>
              )}

              <div className="actions">
                <Magnet strength={10} className="actions-magnet">
                  <button className="primary btn-shimmer" onClick={reset}>
                    Analyze another
                  </button>
                </Magnet>
                <button className="ghost" onClick={handleCopy}>
                  {copied ? <Check size={15} weight="bold" aria-hidden="true" /> : <Copy size={15} weight="bold" aria-hidden="true" />}{" "}
                  {copied ? "Copied" : "Copy result"}
                </button>
              </div>
            </Card.Content>
          </Card>

          <Card className="rise" style={riseDelay(90)}>
            <Card.Header>
              <Card.Title>Flagged source</Card.Title>
              <Card.Description>
                {result.claims.length === 0
                  ? "No sentences matched the rubric, so nothing is highlighted."
                  : `${result.claims.length} flagged claim${result.claims.length > 1 ? "s" : ""} highlighted below.`}{" "}
                Quotes are verbatim. Anything we cannot check says <em>cannot verify</em>.
              </Card.Description>
            </Card.Header>
            <Card.Content>{highlightTranscript(sourceText, result.claims)}</Card.Content>
          </Card>

          <Card className="rise" style={riseDelay(140)}>
            <Card.Header>
              <Card.Title>Flagged claims ({result.claims.length})</Card.Title>
              <Card.Description>Each claim carries its rubric reason.</Card.Description>
            </Card.Header>
            <Card.Content>
              {result.claims.length === 0 ? (
                <p className="lede">
                  Clean pass. No guaranteed returns, urgency tricks, or paid-group
                  pushes detected in this text.
                </p>
              ) : (
                <ul className="claims">
                  {result.claims.map((c, i) => (
                    <li key={i} className="claim">
                      <blockquote>&ldquo;{c.quote}&rdquo;</blockquote>
                      <div className="claim-meta">
                        <span className="type-pill">
                          {CLAIM_TYPE_LABELS[c.claim_type] ?? c.claim_type}
                        </span>
                        {c.flags.map((f) => (
                          <span key={f} className="mini-flag">
                            {f.replace(/_/g, " ")}
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

          <Card className="rise" style={riseDelay(190)}>
            <Card.Header>
              <Card.Title>What to do next</Card.Title>
              <Card.Description>Plain-language guidance, not advice.</Card.Description>
            </Card.Header>
            <Card.Content>
              <ul className="next">
                {NEXT_STEPS[result.classification].map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
              <h3 className="sub-h">Verify on official sources</h3>
              <ul className="verify">
                {result.verification.map((v) => (
                  <li key={v.label} className="v-row">
                    <div>
                      <div className="v-head">
                        <strong>{v.label}</strong>
                        <span className={`status status-${v.status}`}>
                          {v.status.replace("_", " ")}
                        </span>
                      </div>
                      <p>{v.note}</p>
                    </div>
                    <a href={v.url} target="_blank" rel="noreferrer" className="v-link">
                      Official page <ArrowSquareOut size={14} weight="bold" aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ul>
            </Card.Content>
          </Card>

          <Card className="privacy-box rise" style={riseDelay(240)}>
            <Card.Header>
              <Card.Title>Privacy and uncertainty</Card.Title>
            </Card.Header>
            <Card.Content>
              <p>
                Your text was processed in memory and not stored. This tool spots{" "}
                <strong>promotional patterns</strong>. It cannot prove something true
                or false, confirm SEBI registration, or validate a circular from text
                alone. When in doubt it says <em>cannot verify</em>.
              </p>
              <p className="disclaimer-line">{result.disclaimer}</p>
            </Card.Content>
          </Card>
        </main>
      )}

      <footer className="footer">
        <span>Sachet: promotion vs education analyzer, built for Sangyan 2026 Track E. Rubric v1.1.</span>
        <span>{result?.disclaimer ?? OFFLINE_DEMO.disclaimer}</span>
      </footer>
    </div>
  );
}
