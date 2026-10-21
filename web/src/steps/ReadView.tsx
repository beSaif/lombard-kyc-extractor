import { useMemo, useState } from "react";
import { Figure } from "../Figure";
import { confColor, cx } from "../lib";
import type { Step, Word } from "../types";
import { Badge, KV, Pre, Section, Toggle } from "../ui";

/** SVG overlay of OCR word boxes, coordinates as 0..1 fractions of the image. */
export function WordOverlay({
  words,
  byConf,
  hover,
  setHover,
  highlightText,
}: {
  words: Word[];
  byConf: boolean;
  hover: number | null;
  setHover: (i: number | null) => void;
  highlightText?: string | null;
}) {
  const hw = hover !== null ? words[hover] : null;
  return (
    <>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
        {words.map((w, i) => {
          const [x0, y0, x1, y1] = w.b;
          const col = byConf ? confColor(w.c) : "var(--accent)";
          const lit = i === hover || (highlightText && w.t === highlightText);
          return (
            <rect
              key={i}
              x={x0}
              y={y0}
              width={Math.max(0.001, x1 - x0)}
              height={Math.max(0.001, y1 - y0)}
              fill={col}
              fillOpacity={lit ? 0.35 : 0.1}
              stroke={col}
              strokeWidth={lit ? 2 : 1}
              vectorEffect="non-scaling-stroke"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "crosshair" }}
            />
          );
        })}
      </svg>
      {hw && (
        <div
          className="pointer-events-none absolute z-10 rounded border border-line-strong bg-panel px-1.5 py-0.5 text-[11px] whitespace-nowrap shadow"
          style={{ left: `${hw.b[0] * 100}%`, top: `calc(${hw.b[3] * 100}% + 3px)` }}
        >
          <span className="mono font-semibold">{hw.t}</span>
          <span className="ml-2" style={{ color: confColor(hw.c) }}>
            {hw.c === null ? "conf n/a (text layer)" : `conf ${hw.c.toFixed(1)}`}
          </span>
        </div>
      )}
    </>
  );
}

// TD3 line-2 layout (1-based positions): what each character means.
const L2_SEGMENTS: { from: number; to: number; label: string; check?: boolean }[] = [
  { from: 1, to: 9, label: "document number" },
  { from: 10, to: 10, label: "check: doc no.", check: true },
  { from: 11, to: 13, label: "nationality" },
  { from: 14, to: 19, label: "date of birth YYMMDD" },
  { from: 20, to: 20, label: "check: DOB", check: true },
  { from: 21, to: 21, label: "sex" },
  { from: 22, to: 27, label: "expiry YYMMDD" },
  { from: 28, to: 28, label: "check: expiry", check: true },
  { from: 29, to: 42, label: "personal number" },
  { from: 43, to: 43, label: "check: personal no.", check: true },
  { from: 44, to: 44, label: "composite check", check: true },
];
const L1_SEGMENTS = [
  { from: 1, to: 1, label: "doc type P" },
  { from: 2, to: 2, label: "subtype" },
  { from: 3, to: 5, label: "issuing state" },
  { from: 6, to: 44, label: "SURNAME<<GIVEN<NAMES" },
];
const SEG_TINT = ["var(--info-weak)", "var(--accent-weak)"];

function segOf(segs: typeof L2_SEGMENTS, pos: number) {
  const i = segs.findIndex((s) => pos >= s.from && pos <= s.to);
  return { seg: segs[i], i };
}

/** 44-character MRZ lines on a character grid with a position ruler and field segments. */
export function MrzRuler({ lines, compare }: { lines: (string | null)[]; compare?: (string | null)[] }) {
  const [hover, setHover] = useState<{ line: number; pos: number } | null>(null);
  const hoverSeg = hover ? segOf(hover.line === 0 ? L1_SEGMENTS : L2_SEGMENTS, hover.pos).seg : null;
  return (
    <div className="mono overflow-x-auto text-[12px]">
      <div className="flex">
        <span className="w-6 shrink-0" />
        {Array.from({ length: 44 }, (_, i) => (
          <span key={i} className="w-[15px] shrink-0 text-center text-[9px] text-faint">
            {(i + 1) % 5 === 0 || i === 0 ? i + 1 : "·"}
          </span>
        ))}
      </div>
      {lines.map((line, li) => {
        const segs = li === 0 ? L1_SEGMENTS : L2_SEGMENTS;
        const chars = (line ?? "").split("");
        const bad = line !== null && line.length !== 44;
        return (
          <div key={li} className="flex items-center">
            <span className="w-6 shrink-0 text-[10px] text-faint">L{li + 1}</span>
            {Array.from({ length: Math.max(44, chars.length) }, (_, i) => {
              const ch = chars[i];
              const { seg, i: si } = segOf(segs, i + 1);
              const diff = compare && compare[li] && compare[li]![i] !== ch;
              return (
                <span
                  key={i}
                  onMouseEnter={() => setHover({ line: li, pos: i + 1 })}
                  onMouseLeave={() => setHover(null)}
                  className={cx(
                    "w-[15px] shrink-0 border-y border-r border-line text-center leading-[20px]",
                    i === 0 && "border-l",
                    i >= 44 && "text-bad",
                    diff && "text-bad font-bold underline",
                  )}
                  style={{
                    background: seg?.check ? "var(--warn-weak)" : seg ? SEG_TINT[si % 2] : "var(--bad-weak)",
                    outline: hover && hover.line === li && hover.pos === i + 1 ? "1px solid var(--accent)" : undefined,
                  }}
                >
                  {ch ?? <span className="text-bad">∅</span>}
                </span>
              );
            })}
            <span className={cx("ml-2 text-[10px]", bad ? "text-bad" : "text-faint")}>{line === null ? "null" : `${line.length} chars`}</span>
          </div>
        );
      })}
      <div className="mt-1 h-4 text-[11px] text-muted">
        {hover && hoverSeg ? (
          <>
            L{hover.line + 1} pos {hover.pos}: <span className="text-fg">{hoverSeg.label}</span>
          </>
        ) : (
          <span className="text-faint">Hover a character. Amber cells are check digits (ICAO 9303, weights 7-3-1, mod 10).</span>
        )}
      </div>
    </div>
  );
}

export function ReadView({ step }: { step: Step }) {
  const d = step.data;
  const words: Word[] = d.words ?? [];
  const [byConf, setByConf] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [hover, setHover] = useState<number | null>(null);
  const [lit, setLit] = useState<string | null>(null);
  const isText = d.source === "text_layer";
  const buckets = useMemo(() => {
    const b = { low: 0, mid: 0, high: 0, none: 0 };
    for (const w of words) {
      if (w.c === null) b.none++;
      else if (w.c < 60) b.low++;
      else if (w.c < 85) b.mid++;
      else b.high++;
    }
    return b;
  }, [words]);
  const overlay = showBoxes ? <WordOverlay words={words} byConf={byConf} hover={hover} setHover={setHover} highlightText={lit} /> : undefined;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {isText ? (
          <Badge tone="ok">text layer: exact text from the PDF, no OCR</Badge>
        ) : (
          <Badge tone="accent">OCR · Tesseract {(d.languages ?? []).join("+")}</Badge>
        )}
        <Badge mono>page {d.page}</Badge>
        <Badge mono>{words.length} words</Badge>
        {d.mean_confidence != null && (
          <Badge mono tone={d.mean_confidence >= 85 ? "ok" : d.mean_confidence >= 60 ? "warn" : "bad"}>mean conf {d.mean_confidence}</Badge>
        )}
        <span className="ml-auto flex gap-3">
          <Toggle checked={showBoxes} onChange={setShowBoxes} label="word boxes" />
          <Toggle checked={byConf} onChange={setByConf} label="colour by confidence" />
        </span>
      </div>
      <div className="grid gap-3 @4xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div>
          <Figure
            src={d.image}
            overlay={overlay}
            caption={
              <span className="flex flex-wrap gap-3">
                <span>Boxes are 0–1 fractions of this image (the flattened page). Hover a box for text + confidence.</span>
                {byConf && !isText && (
                  <span className="flex gap-2">
                    <span style={{ color: "var(--bad)" }}>■ &lt;60</span>
                    <span style={{ color: "var(--warn)" }}>■ 60–85</span>
                    <span style={{ color: "var(--ok)" }}>■ ≥85</span>
                  </span>
                )}
              </span>
            }
          />
        </div>
        <div className="flex min-w-0 flex-col gap-3">
          {!isText && (
            <Section title="Confidence distribution">
              <div className="flex h-3 overflow-hidden rounded-sm border border-line">
                {(["low", "mid", "high"] as const).map((k) => (
                  <div
                    key={k}
                    title={`${k}: ${buckets[k]}`}
                    style={{
                      width: `${(buckets[k] / Math.max(1, words.length)) * 100}%`,
                      background: k === "low" ? "var(--bad)" : k === "mid" ? "var(--warn)" : "var(--ok)",
                    }}
                  />
                ))}
              </div>
              <div className="mono mt-1 flex gap-3 text-[11px] text-muted">
                <span>&lt;60: {buckets.low}</span>
                <span>60–85: {buckets.mid}</span>
                <span>≥85: {buckets.high}</span>
                {buckets.none > 0 && <span>n/a: {buckets.none}</span>}
              </div>
              {(d.low_confidence ?? []).length > 0 && (
                <>
                  <div className="mt-2 mb-1 text-[11px] text-muted">Low-confidence words (&lt;60), hover to locate:</div>
                  <div className="flex flex-wrap gap-1">
                    {(d.low_confidence as string[]).map((w, i) => (
                      <span
                        key={i}
                        onMouseEnter={() => setLit(w)}
                        onMouseLeave={() => setLit(null)}
                        className="mono cursor-default rounded bg-bad-weak px-1 text-[11px] text-bad"
                      >
                        {w}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </Section>
          )}
          <Section title={isText ? "Text layer (reading order)" : "Reconstructed text (words_to_text)"} pad={false}>
            <Pre className="rounded-none border-0" maxH={380}>
              {d.text}
            </Pre>
          </Section>
          {"mrz" in d && (
            <Section title="MRZ pass (dedicated OCR, 37-char whitelist)">
              {d.mrz ? <MrzRuler lines={d.mrz} /> : <div className="text-[12px] text-muted">The MRZ pass found no two 44-char lines (null). The model's reading will be used.</div>}
            </Section>
          )}
          {!isText && (
            <KV
              rows={[
                ["languages", (d.languages ?? []).join(", ")],
                ["image", <a className="text-accent hover:underline" href={d.image} target="_blank">{d.image}</a>],
              ]}
            />
          )}
        </div>
      </div>
    </div>
  );
}
