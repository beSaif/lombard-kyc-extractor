import { useEffect, useMemo, useRef, useState } from "react";
import { api, lsGet, lsSet, previewUrl, useFetch } from "../api";
import { CodePanel } from "../Code";
import { Figure } from "../Figure";
import { DEFECTS, DOCS, DOC_LABEL, MODE_INFO, TIERS, TIER_INFO, TRAPS, cx, ms, usd } from "../lib";
import { navigate, setParams, type Route } from "../router";
import { DecisionBadge } from "../steps/ChecksView";
import { ReviewBadge, ReviewView } from "../steps/ReviewView";
import { KIND_ICON, StepDetail } from "../steps/StepDetail";
import { SummaryView } from "../steps/SummaryView";
import type { CaseSummary, CaseTier, Extractor, RunListItem, RunState, Step, Tier } from "../types";
import { Badge, Empty, ErrorBox, Section, Spinner, Tabs } from "../ui";

export const LS_EXTRACTOR = "kyc.extractor";

export function extractorLabel(e: Extractor): string {
  const price = e.price ? ` · $${e.price[0]}/$${e.price[1]} per 1M` : e.local ? " · free, local" : "";
  return `${e.provider === "rules" ? "rules (regex baseline)" : `${e.model}`} · ${e.mode}${price}`;
}

export function ExtractorSelect({
  value,
  onChange,
  extractors,
  allowNone,
}: {
  value: string;
  onChange: (v: string) => void;
  extractors: Extractor[];
  allowNone?: boolean;
}) {
  const groups: [string, Extractor[]][] = [
    ["Local (Ollama)", extractors.filter((e) => e.provider === "ollama")],
    ["OpenAI", extractors.filter((e) => e.provider === "openai")],
    ["Baseline", extractors.filter((e) => e.provider === "rules")],
    ["Other", extractors.filter((e) => !["ollama", "openai", "rules"].includes(e.provider))],
  ];
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cx("mono h-8 rounded-md border border-line bg-panel px-2 text-[12px]", allowNone ? "max-w-[230px]" : "max-w-[320px]")} 
    >
      {allowNone && <option value="">none</option>}
      {!extractors.some((e) => e.spec === value) && value && <option value={value}>{value}</option>}
      {groups
        .filter(([, es]) => es.length)
        .map(([g, es]) => (
          <optgroup key={g} label={g}>
            {es.map((e) => (
              <option key={e.spec} value={e.spec}>
                {extractorLabel(e)}
              </option>
            ))}
          </optgroup>
        ))}
    </select>
  );
}

function CaseBadges({ c, compact }: { c: { defects: string[]; traps: string[] }; compact?: boolean }) {
  return (
    <span className="flex flex-wrap gap-1">
      {c.defects.length === 0 && !compact && <Badge tone="ok">no defect</Badge>}
      {c.defects.map((d) => (
        <Badge key={d} mono tone="bad" title={DEFECTS[d]}>
          {d}
        </Badge>
      ))}
      {c.traps.map((t) => (
        <Badge key={t} mono tone="warn" title={TRAPS[t]}>
          {t}
        </Badge>
      ))}
    </span>
  );
}

function CasePicker({ cases, value, onChange }: { cases: CaseSummary[]; value: string; onChange: (c: string) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const on = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", on);
    return () => document.removeEventListener("mousedown", on);
  }, []);
  const cur = cases.find((c) => c.case === value);
  const shown = cases.filter((c) => !q || [c.case, ...c.defects, ...c.traps, ...Object.values(c.layouts)].join(" ").toLowerCase().includes(q.toLowerCase()));
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex h-8 max-w-[520px] items-center gap-2 rounded-md border border-line bg-panel px-2 text-left">
        <span className="mono font-medium">{value}</span>
        {cur && (
          <span className="flex min-w-0 gap-1 overflow-hidden whitespace-nowrap">
            {cur.defects.map((d) => (
              <Badge key={d} mono tone="bad" title={DEFECTS[d]}>
                {d}
              </Badge>
            ))}
            {cur.defects.length === 0 && <Badge tone="ok">no defect</Badge>}
            {cur.traps.length > 0 && (
              <Badge mono tone="warn" title={cur.traps.join(", ")}>
                {cur.traps.length} trap{cur.traps.length > 1 ? "s" : ""}
              </Badge>
            )}
          </span>
        )}
        <span className="text-faint">▾</span>
      </button>
      {open && (
        <div className="absolute top-9 left-0 z-40 w-[680px] rounded-md border border-line-strong bg-panel shadow-lg">
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="filter: case id, defect, trap, layout (e.g. MRZ, de/letter)"
            className="w-full border-b border-line bg-transparent px-3 py-2 text-[12px] outline-none"
          />
          <div className="max-h-[60vh] overflow-auto">
            {shown.map((c) => (
              <button
                key={c.case}
                onClick={() => {
                  onChange(c.case);
                  setOpen(false);
                }}
                className={cx("flex w-full items-start gap-3 border-b border-line px-3 py-1.5 text-left last:border-0 hover:bg-sunk", c.case === value && "bg-accent-weak")}
              >
                <span className="mono w-20 shrink-0 pt-0.5 font-medium">{c.case}</span>
                <span className="flex-1">
                  {(c.suite === "hard" || c.suite === "blind") && (
                    <Badge tone="accent" className="mr-1" title={c.suite === "hard" ? "Hard suite: built to break the system" : "Blind suite: written without seeing the rules"}>
                      {c.suite}
                    </Badge>
                  )}
                  <CaseBadges c={c} />
                </span>
                <span className="mono shrink-0 pt-0.5 text-[11px] text-faint">
                  A {c.layouts.form_a} · PoA {c.layouts.proof_of_address}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PreRun({ tier, caseId }: { tier: CaseTier; caseId: string }) {
  const det = useFetch(`case:${tier}/${caseId}`, () => api.caseDetail(tier, caseId));
  const t = det.data?.truth ?? undefined;
  const present = (d: string) => !det.data || det.data.files.some((f) => f.startsWith(`${d}.`));
  return (
    <div className="flex flex-col gap-3 p-4">
      {tier === "upload" && (
        <div className="rounded border-l-2 border-accent bg-accent-weak px-3 py-2 text-[12px]">
          Your own documents. There is no truth to score against: run them, then open <b>Review</b> to check every value by eye and sign off.
          They stay on this machine unless you pick a cloud model.
        </div>
      )}
      <div className="grid grid-cols-3 gap-3">
        {DOCS.map((d) =>
          present(d) ? (
            <Figure key={`${tier}${caseId}${d}`} src={previewUrl(tier, caseId, d, 900)} caption={`${DOC_LABEL[d]} · ${tier}/${caseId}${t?.layouts[d] ? ` · layout ${t.layouts[d]}` : ""}`} maxH={460} />
          ) : (
            <div key={d} className="rounded border border-dashed border-line p-6 text-center text-[12px] text-faint">
              no {DOC_LABEL[d].toLowerCase()} uploaded: it will be flagged MISSING_DOCUMENT
            </div>
          ),
        )}
      </div>
      {det.error && <ErrorBox>{det.error}</ErrorBox>}
      {t && (
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div className="flex flex-col gap-3">
            <Section title="Expected flags (truth.json)">
              {t.expected_flags.length === 0 ? (
                <div className="text-[12px]">
                  <DecisionBadge decision="pre_filled_review" /> <span className="text-muted">no defect: should go straight through</span>
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  <div>
                    <DecisionBadge decision="manual_review" />
                  </div>
                  {t.expected_flags.map((f) => (
                    <div key={f} className="flex items-start gap-2 text-[12px]">
                      <Badge mono tone="bad">
                        {f}
                      </Badge>
                      <span className="text-muted">{DEFECTS[f]}</span>
                    </div>
                  ))}
                </div>
              )}
            </Section>
            <Section title="Traps (harmless variations; must NOT be flagged)">
              {t.traps.length === 0 ? (
                <div className="text-[12px] text-faint">none</div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  {t.traps.map((f) => (
                    <div key={f} className="flex items-start gap-2 text-[12px]">
                      <Badge mono tone="warn">
                        {f}
                      </Badge>
                      <span className="text-muted">{TRAPS[f]}</span>
                    </div>
                  ))}
                </div>
              )}
            </Section>
            <div className="text-[11px] text-muted">
              Review date (as_of): <span className="mono">{t.as_of ?? "2026-10-21"}</span>
            </div>
          </div>
          <Section title="True field values" pad={false}>
            <table className="dt text-[12px]">
              <tbody>
                {DOCS.map((d) =>
                  Object.entries(t.fields[d] ?? {}).map(([f, v], i) => (
                    <tr key={d + f}>
                      <td className="w-[1%] whitespace-nowrap text-muted">{i === 0 ? DOC_LABEL[d] : ""}</td>
                      <td className="mono w-[1%] whitespace-nowrap">{f}</td>
                      <td className="mono break-all">{v ?? <span className="text-faint">null</span>}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </Section>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- run view

type Sel = number | "summary" | "review";

function groupSteps(steps: Step[]) {
  const groups: { key: string; label: string; steps: Step[] }[] = [
    ...DOCS.map((d) => ({ key: d, label: DOC_LABEL[d], steps: steps.filter((s) => s.doc === d) })),
    { key: "file", label: "Whole file", steps: steps.filter((s) => !s.doc) },
  ];
  return groups;
}

/** Steps run by the second model: prompt/llm/normalise after the doc's ground step. */
function secondModelIds(steps: Step[]): Set<number> {
  const out = new Set<number>();
  for (const d of DOCS) {
    const ds = steps.filter((s) => s.doc === d);
    const g = ds.find((s) => s.kind === "ground");
    if (!g) continue;
    ds.filter((s) => s.id > g.id && ["prompt", "llm", "normalise", "extract"].includes(s.kind)).forEach((s) => out.add(s.id));
  }
  return out;
}

function Timeline({
  steps,
  sel,
  onSelect,
  running,
  done,
  animate,
  second,
}: {
  steps: Step[];
  sel: Sel | null;
  onSelect: (s: Sel) => void;
  running: boolean;
  done: boolean;
  animate: boolean;
  second: Set<number>;
}) {
  const groups = groupSteps(steps);
  const last = steps[steps.length - 1];
  const inFlight = last && last.ms === null;
  return (
    <div className="flex flex-col gap-2 p-2">
      {done && (
        <button
          onClick={() => onSelect("summary")}
          className={cx(
            "flex items-center gap-2 rounded-md border px-2 py-1.5 text-left",
            sel === "summary" ? "border-accent bg-accent-weak" : "border-line bg-panel hover:bg-sunk",
            animate && "step-in",
          )}
        >
          <span className="w-4 text-center text-accent">Σ</span>
          <span className="flex-1 font-medium">Summary</span>
          <span className="text-[11px] text-muted">vs truth</span>
        </button>
      )}
      {done && (
        <button
          onClick={() => onSelect("review")}
          className={cx(
            "flex items-center gap-2 rounded-md border px-2 py-1.5 text-left",
            sel === "review" ? "border-accent bg-accent-weak" : "border-line bg-panel hover:bg-sunk",
            animate && "step-in",
          )}
        >
          <span className="w-4 text-center text-accent">✎</span>
          <span className="flex-1 font-medium">Review</span>
          <span className="text-[11px] text-muted">human sign-off</span>
        </button>
      )}
      {groups.map((g) => {
        const started = g.steps.length > 0;
        if (!started && !running) return null;
        return (
          <div key={g.key}>
            <div className={cx("flex items-center gap-2 px-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider", started ? "text-muted" : "text-faint")}>
              {g.label}
              {started && (
                <span className="mono font-normal normal-case tracking-normal text-faint">
                  {ms(g.steps.reduce((a, s) => a + (s.ms ?? 0), 0))}
                </span>
              )}
              {!started && <span className="font-normal normal-case tracking-normal">waiting</span>}
            </div>
            <div className="flex flex-col">
              {g.steps.map((s) => {
                const isRun = s.ms === null;
                return (
                  <button
                    key={s.id}
                    onClick={() => onSelect(s.id)}
                    className={cx(
                      "group flex items-center gap-2 rounded px-1.5 py-1 text-left",
                      sel === s.id ? "bg-accent-weak text-fg" : "hover:bg-sunk",
                      animate && "step-in",
                    )}
                  >
                    <span className={cx("w-4 shrink-0 text-center", s.status === "error" ? "text-bad" : "text-accent")}>{KIND_ICON[s.kind] ?? "•"}</span>
                    <span className="min-w-0 flex-1 truncate text-[12.5px]">
                      {s.title}
                      {second.has(s.id) && <span className="ml-1 text-[10px] text-info">2nd</span>}
                    </span>
                    {isRun ? (
                      <Spinner size={11} />
                    ) : (
                      <span className={cx("mono shrink-0 text-[10.5px] tabular", (s.ms ?? 0) > 1000 ? "text-warn" : "text-faint")}>{ms(s.ms)}</span>
                    )}
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: s.status === "error" ? "var(--bad)" : isRun ? "var(--line-strong)" : "var(--ok)" }}
                    />
                  </button>
                );
              })}
              {running && !inFlight && last && (last.doc ?? "file") === g.key && (
                <div className="flex items-center gap-2 px-1.5 py-1 text-[12px] text-faint">
                  <Spinner size={11} /> next step…
                </div>
              )}
            </div>
          </div>
        );
      })}
      {running && steps.length === 0 && (
        <div className="flex items-center gap-2 px-1.5 py-1 text-[12px] text-faint">
          <Spinner size={11} /> starting…
        </div>
      )}
    </div>
  );
}

function RunView({ runId, initialStep, showCode, setShowCode }: { runId: string; initialStep?: string; showCode: boolean; setShowCode: (v: boolean) => void }) {
  const [run, setRun] = useState<RunState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<Sel | null>(
    initialStep ? (initialStep === "summary" || initialStep === "review" ? initialStep : +initialStep) : null,
  );
  const [follow, setFollow] = useState(!initialStep);
  const [wasRunning, setWasRunning] = useState(false);
  const [clock, setClock] = useState<{ base: number; at: number } | null>(null);
  const [, tick] = useState(0);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    setRun(null);
    setErr(null);
    const poll = async () => {
      try {
        const r = await api.run(runId);
        if (!alive) return;
        setRun(r);
        if (r.status === "running") {
          setWasRunning(true);
          setClock({ base: r.elapsed ?? 0, at: Date.now() });
          timer = window.setTimeout(poll, 700);
        }
      } catch (e) {
        if (alive) setErr((e as Error).message);
      }
    };
    poll();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [runId]);

  const running = run?.status === "running";
  useEffect(() => {
    if (!running) return;
    const i = window.setInterval(() => tick((t) => t + 1), 100);
    return () => window.clearInterval(i);
  }, [running]);

  const steps: Step[] = useMemo(() => run?.steps ?? run?.result?.steps ?? [], [run]);
  const result = run?.result;
  const done = run?.status === "done" && !!result;

  // Auto-follow: latest step while running; the summary once done.
  useEffect(() => {
    if (!follow) return;
    if (done) setSel("summary");
    else if (steps.length) setSel(steps[steps.length - 1].id);
  }, [follow, done, steps]);

  const select = (s: Sel) => {
    setFollow(false);
    setSel(s);
    setParams({ step: String(s) });
  };

  const second = useMemo(() => secondModelIds(steps), [steps]);
  const step = typeof sel === "number" ? steps.find((s) => s.id === sel) : undefined;
  const elapsed = running && clock ? clock.base + (Date.now() - clock.at) / 1000 : run?.elapsed ?? result?.totals.seconds;
  const codeRefs =
    sel === "summary"
      ? ["kyc_demo.pipeline.run_case", "kyc_demo.evaluate.score_case"]
      : sel === "review"
        ? ["kyc_demo.review.review_state", "kyc_demo.review.refuse_decision", "kyc_demo.review.AuditLog.append"]
        : step?.code ?? [];
  const req = run?.request ?? result?.request;

  if (err) return <div className="p-4"><ErrorBox>{err}</ErrorBox></div>;
  if (!run)
    return (
      <div className="flex items-center gap-2 p-6 text-muted">
        <Spinner /> loading run {runId}
      </div>
    );

  return (
    <div
      className="grid min-h-0 flex-1"
      style={{ gridTemplateColumns: showCode ? "250px minmax(0,1fr) clamp(360px, 32vw, 640px)" : "250px minmax(0,1fr) 34px" }}
    >
      <aside className="min-h-0 overflow-auto border-r border-line bg-panel">
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-line bg-panel px-3 py-2">
          {running ? <Spinner /> : run.status === "error" ? <Badge tone="bad">error</Badge> : <Badge tone="ok">done</Badge>}
          <span className="mono text-[12px] tabular">{elapsed != null ? `${elapsed.toFixed(1)} s` : ""}</span>
          <span className="mono ml-auto text-[11px] text-faint">{steps.length} steps</span>
        </div>
        {req && (
          <div className="mono border-b border-line px-3 py-1.5 text-[10.5px] leading-[1.5] text-muted">
            <div className="truncate" title={runId}>{runId}</div>
            <div className="truncate">
              {req.tier}/{req.case} · {req.reader}
            </div>
            <div className="truncate" title={req.extractor}>{req.extractor}</div>
            {req.second && <div className="truncate text-info">+ {req.second}</div>}
          </div>
        )}
        {follow && running && <div className="px-3 pt-1.5 text-[11px] text-faint">following the latest step; click a step to pin it</div>}
        <Timeline steps={steps} sel={sel} onSelect={select} running={running} done={done} animate={wasRunning} second={second} />
      </aside>
      <main className="@container min-h-0 overflow-auto p-4">
        {run.status === "error" && <ErrorBox>{run.error}</ErrorBox>}
        {sel === "summary" && result ? (
          <SummaryView result={result} />
        ) : sel === "review" && result ? (
          <ReviewView result={result} steps={steps} />
        ) : step ? (
          <StepDetail key={step.id} step={step} ctx={{ steps, result, request: req }} secondModel={second.has(step.id)} />
        ) : (
          <Empty>Waiting for the first step…</Empty>
        )}
      </main>
      <aside className="flex min-h-0 flex-col border-l border-line bg-panel">
        {showCode ? (
          <>
            <div className="flex items-center gap-2 border-b border-line px-3 py-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">Code behind this step</span>
              <button className="ml-auto rounded px-1.5 text-[12px] text-muted hover:bg-sunk hover:text-fg" onClick={() => setShowCode(false)} title="Hide code panel">
                ▸ hide
              </button>
            </div>
            <div className="flex min-h-0 flex-1 flex-col overflow-auto p-3">
              <CodePanel refs={codeRefs} />
            </div>
          </>
        ) : (
          <button className="flex h-full flex-col items-center gap-2 pt-3 text-[11px] text-muted hover:bg-sunk hover:text-fg" onClick={() => setShowCode(true)} title="Show code panel">
            ◂<span style={{ writingMode: "vertical-rl" }}>Code</span>
          </button>
        )}
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- recent runs

function RecentRuns({ onClose }: { onClose: () => void }) {
  const runs = useFetch<RunListItem[]>("runs", api.runs, false);
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div className="flex h-full w-[560px] flex-col border-l border-line bg-panel shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <h3 className="font-semibold">Recent runs</h3>
          <span className="text-[12px] text-muted">{runs.data?.length ?? ""} on disk (runs/*/result.json)</span>
          <button className="ml-auto rounded border border-line px-2 py-0.5 text-[12px] hover:bg-sunk" onClick={runs.reload}>
            refresh
          </button>
          <button className="rounded border border-line px-2 py-0.5 text-[12px] hover:bg-sunk" onClick={onClose}>
            close
          </button>
        </div>
        <div className="flex-1 overflow-auto">
          {runs.loading && !runs.data && (
            <div className="p-4">
              <Spinner />
            </div>
          )}
          {runs.error && <ErrorBox>{runs.error}</ErrorBox>}
          {runs.data?.length === 0 && <Empty>No finished runs yet.</Empty>}
          {runs.data?.map((r) => (
            <button
              key={r.run_id}
              onClick={() => {
                navigate("pipeline", { tier: r.tier, case: r.case, extractor: r.extractor, second: r.second, run: r.run_id });
                onClose();
              }}
              className="flex w-full flex-col gap-1 border-b border-line px-4 py-2 text-left hover:bg-sunk"
            >
              <div className="flex items-center gap-2">
                <span className="mono text-[12px] font-medium">
                  {r.tier}/{r.case}
                </span>
                <DecisionBadge decision={r.decision} />
                {r.review && r.review !== "open" && <ReviewBadge status={r.review} />}
                <span className="mono ml-auto text-[11px] text-faint">{r.run_id}</span>
              </div>
              <div className="mono truncate text-[11px] text-muted">
                {r.extractor}
                {r.second ? ` + ${r.second}` : ""} · {r.totals.seconds}s · {r.totals.cost_usd ? usd(r.totals.cost_usd) : "free"}
              </div>
              {r.flags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {r.flags.map((f, i) => (
                    <Badge key={i} mono tone={f in DEFECTS ? "bad" : "neutral"}>
                      {f}
                    </Badge>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- upload

function UploadDialog({ onClose, onDone }: { onClose: () => void; onDone: (caseId: string) => void }) {
  const [files, setFiles] = useState<Record<string, File>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      onDone((await api.upload(files)).case);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="flex w-[520px] max-w-[calc(100vw-32px)] flex-col gap-3 rounded-md border border-line bg-panel p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold">Upload a client file</h3>
        <p className="text-[12px] text-muted">
          PDF, JPEG or PNG, up to 20 MB each. A missing document is flagged, not guessed. Files are stored under runs/uploads on this machine and only
          leave it if you run a cloud model on them.
        </p>
        {DOCS.map((d) => (
          <label key={d} className="flex items-center gap-3 text-[12px]">
            <span className="w-32 font-medium">{DOC_LABEL[d]}</span>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => {
                const f = e.target.files?.[0];
                setFiles((cur) => {
                  const next = { ...cur };
                  if (f) next[d] = f;
                  else delete next[d];
                  return next;
                });
              }}
            />
          </label>
        ))}
        {err && <ErrorBox>{err}</ErrorBox>}
        <div className="flex justify-end gap-2">
          <button className="h-8 rounded-md border border-line px-3 text-[12px] hover:bg-sunk" onClick={onClose}>
            Cancel
          </button>
          <button
            disabled={busy || Object.keys(files).length === 0}
            onClick={submit}
            className="h-8 rounded-md bg-accent px-4 text-[12px] font-semibold text-white disabled:opacity-50 dark:text-black"
          >
            {busy ? "Uploading…" : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- page

export function PipelinePage({ route }: { route: Route }) {
  const p = route.params;
  const tier = (TIERS.includes(p.tier as Tier) || p.tier === "upload" ? p.tier : "scan") as CaseTier;
  const caseId = p.case || "case_001";
  const cases = useFetch("cases", api.cases);
  const extractors = useFetch("extractors", api.extractors);
  // Local first: nothing leaves the machine unless someone picks a cloud model.
  const localDefault = extractors.data?.find((e) => e.provider === "ollama" && e.mode === "both")?.spec ?? "rules";
  const extractor = p.extractor || lsGet(LS_EXTRACTOR) || localDefault;
  const second = p.second || "";
  const reader = (p.reader || "auto") as "auto" | "text" | "ocr";
  const runId = p.run;
  const [starting, setStarting] = useState(false);
  const [startErr, setStartErr] = useState<string | null>(null);
  const [showRuns, setShowRuns] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [showCode, setShowCodeState] = useState(() => lsGet("kyc.showCode") !== "0");
  const setShowCode = (v: boolean) => {
    setShowCodeState(v);
    lsSet("kyc.showCode", v ? "1" : "0");
  };

  const tierCases = (cases.data ?? []).filter((c) => c.tier === tier);
  const ex = extractors.data?.find((e) => e.spec === extractor);

  const change = (patch: Record<string, string | null>) => setParams({ ...patch, run: null, step: null }, false);

  const start = async () => {
    setStarting(true);
    setStartErr(null);
    try {
      const { run_id } = await api.startRun({ tier, case: caseId, extractor, second: second || null, reader });
      setParams({ tier, case: caseId, extractor, second: second || null, reader, run: run_id, step: null }, false);
    } catch (e) {
      setStartErr((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-col gap-2 border-b border-line bg-panel px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-2">
            <Tabs
              tabs={[...TIERS.map((t) => ({ id: t as CaseTier, label: t, title: TIER_INFO[t] })), ...(tier === "upload" ? [{ id: "upload" as CaseTier, label: "upload" }] : [])]}
              value={tier}
              onChange={(t) => change({ tier: t, case: t === "upload" ? caseId : tier === "upload" ? "case_001" : caseId })}
            />
          </div>
          {tier === "upload" ? (
            <Badge mono tone="accent">
              your upload {caseId}
            </Badge>
          ) : (
            cases.data && <CasePicker cases={tierCases} value={caseId} onChange={(c) => change({ case: c })} />
          )}
          <button onClick={() => setShowUpload(true)} className="h-8 rounded-md border border-line px-3 text-[12px] text-muted hover:bg-sunk hover:text-fg">
            Upload your own…
          </button>
          <label className="flex items-center gap-1.5 text-[12px] text-muted">
            extractor
            {extractors.data && (
              <ExtractorSelect
                value={extractor}
                extractors={extractors.data}
                onChange={(v) => {
                  lsSet(LS_EXTRACTOR, v);
                  change({ extractor: v });
                }}
              />
            )}
          </label>
          <label className="flex items-center gap-1.5 text-[12px] text-muted" title="A second model reads the same documents; fields where the two disagree are flagged MODEL_DISAGREEMENT.">
            second model
            {extractors.data && <ExtractorSelect value={second} allowNone extractors={extractors.data} onChange={(v) => change({ second: v || null })} />}
          </label>
          <label className="flex items-center gap-1.5 text-[12px] text-muted">
            reader
            <select value={reader} onChange={(e) => change({ reader: e.target.value })} className="mono h-8 rounded-md border border-line bg-panel px-2 text-[12px]">
              <option value="auto">auto</option>
              <option value="text">text</option>
              <option value="ocr">ocr</option>
            </select>
          </label>
          <button
            onClick={start}
            disabled={starting}
            className="h-8 rounded-md bg-accent px-4 font-semibold text-white hover:opacity-90 disabled:opacity-50 dark:text-black"
          >
            {starting ? "Starting…" : runId ? "Run again" : "Run ▸"}
          </button>
          <button onClick={() => setShowRuns(true)} className="h-8 rounded-md border border-line px-3 text-[12px] text-muted hover:bg-sunk hover:text-fg">
            Recent runs
          </button>
          {runId && (
            <button onClick={() => change({})} className="h-8 rounded-md border border-line px-3 text-[12px] text-muted hover:bg-sunk hover:text-fg">
              ← case preview
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-0.5 text-[12px] text-muted">
          <span>
            <b className="font-medium text-fg">{tier}</b>: {tier === "upload" ? "your own documents, read as they are" : TIER_INFO[tier]}
          </span>
          <span>
            {ex ? (ex.provider === "rules" ? "rules: hand-written regexes over the OCR text, no model. The baseline." : MODE_INFO[ex.mode]) : ""}
          </span>
          <span>
            reader <b className="font-medium text-fg">{reader}</b>: {reader === "auto" ? "text layer when the PDF has one, else OCR" : reader === "text" ? "always use the text layer" : "always OCR, even born-digital PDFs"}
          </span>
        </div>
        {startErr && <ErrorBox>{startErr}</ErrorBox>}
      </div>
      {runId ? (
        <RunView key={runId} runId={runId} initialStep={p.step} showCode={showCode} setShowCode={setShowCode} />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <PreRun tier={tier} caseId={caseId} />
        </div>
      )}
      {showRuns && <RecentRuns onClose={() => setShowRuns(false)} />}
      {showUpload && (
        <UploadDialog
          onClose={() => setShowUpload(false)}
          onDone={(c) => {
            setShowUpload(false);
            setParams({ tier: "upload", case: c, run: null, step: null }, false);
          }}
        />
      )}
    </div>
  );
}
