import { useEffect, useMemo, useState } from "react";
import { api, useFetch } from "../api";
import { DEFECTS, TIERS, TIER_INFO, TRAPS, cx, isDefect, pct } from "../lib";
import { navigate, setParams, type Route } from "../router";
import { DecisionBadge } from "../steps/ChecksView";
import type { CaseError, CaseScore, EvalReport, Suite, Summary, Tier } from "../types";
import { Badge, Empty, ErrorBox, Section, Spinner, Tabs } from "../ui";

type Kind = "%" | "n" | "$" | "s";
const METRICS: { key: keyof Summary; label: string; kind: Kind; better: "high" | "low"; legend: string }[] = [
  { key: "missed_defect_files", label: "Defect files sent to the quick queue", kind: "n", better: "low", legend: "The dangerous error: a file with a real problem that skipped manual review. Read it next to straight-through: flagging everything scores 0 here and saves nothing." },
  { key: "defect_recall", label: "Defect recall", kind: "%", better: "high", legend: "Planted defects that were flagged, with a 95% interval: with this few defects, 100% only shows recall is probably above the lower bound." },
  { key: "defects_not_flagged", label: "Defects not flagged", kind: "n", better: "low", legend: "Defects whose flag was never raised. The file may still reach manual review for another reason, but then nobody is told what is wrong." },
  { key: "right_check_rate", label: "Defects caught by the right check", kind: "%", better: "high", legend: "Raised by the check meant to catch them, not by another that shares the flag code." },
  { key: "defect_precision", label: "Defect precision", kind: "%", better: "high", legend: "Defect flags raised that were real (process flags not counted)." },
  { key: "trap_false_alarm_rate", label: "Trap false-alarm rate", kind: "%", better: "low", legend: "Harmless variations (Av./Avenue, no middle name) wrongly flagged as a defect." },
  { key: "straight_through_rate", label: "Straight-through (clean files)", kind: "%", better: "high", legend: "Clean files that reached the pre-filled queue. This is the time saved." },
  { key: "routing_accuracy", label: "Routing accuracy", kind: "%", better: "high", legend: "Files sent to the right queue (manual if a defect, pre-filled if clean)." },
  { key: "field_accuracy", label: "Field accuracy", kind: "%", better: "high", legend: "Truth values extracted correctly, after normalisation (dates, ISO codes, names)." },
  { key: "critical_field_accuracy", label: "Critical-field accuracy", kind: "%", better: "high", legend: "Same, over the 12 identity fields (names, DOB, doc number, expiry, addresses, bill date)." },
  { key: "process_flags_per_file", label: "Process flags per file", kind: "n", better: "low", legend: "EVIDENCE_NOT_FOUND, MISSING_FIELD, MODEL_DISAGREEMENT: send clean files to manual review." },
  { key: "errors", label: "Errors", kind: "n", better: "low", legend: "Files whose run crashed. They are left out of every other metric." },
  { key: "seconds_per_file", label: "Seconds per file", kind: "s", better: "low", legend: "Wall time for the three documents, OCR included (cached model calls show original latency)." },
  { key: "cost_per_file_usd", label: "$ per file", kind: "$", better: "low", legend: "API cost for the three documents. Local models and rules are free." },
];

function fmt(v: number | null | undefined, kind: Kind): string {
  if (v === null || v === undefined) return "–";
  if (kind === "%") return pct(v, 1);
  if (kind === "$") return `$${v.toFixed(4)}`;
  if (kind === "s") return `${v.toFixed(2)} s`;
  return String(v);
}

/** Background tint for a 0..1 score in four clear bands, good = green. */
function heat(v: number | null | undefined, goodHigh = true): { background?: string; color?: string } {
  if (v === null || v === undefined) return {};
  const g = goodHigh ? v : 1 - v;
  if (g >= 0.995) return { background: "var(--ok-weak)", color: "var(--ok)" };
  if (g >= 0.8) return { background: "color-mix(in srgb, var(--warn-weak) 55%, transparent)", color: "var(--warn)" };
  if (g >= 0.5) return { background: "var(--warn-weak)", color: "var(--warn)" };
  return { background: "var(--bad-weak)", color: "var(--bad)" };
}

const short = (name: string) => name.replace(/(^|\+)openai:/g, "$1").replace(/(^|\+)ollama:/g, "$1ollama ");

function parseName(name: string) {
  const [main, reader] = name.split("#");
  const [spec, second] = main.split("+");
  return { spec, second: second ?? null, reader: reader ?? null };
}

function Grid({
  title,
  rows,
  reports,
  tier,
  pick,
  goodHigh,
  explain,
}: {
  title: string;
  rows: string[];
  reports: EvalReport[];
  tier: Tier;
  pick: (s: Summary) => Record<string, number | null>;
  goodHigh: boolean;
  explain?: Record<string, string>;
}) {
  return (
    <Section title={title} pad={false}>
      <div className="overflow-x-auto">
        <table className="dt text-[12px]">
          <thead>
            <tr>
              <th></th>
              {reports.map((r) => (
                <th key={r.extractor} className="mono text-center normal-case tracking-normal" title={r.extractor}>
                  {short(r.extractor)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((k) => (
              <tr key={k}>
                <td className="mono whitespace-nowrap" title={explain?.[k]}>
                  {k}
                </td>
                {reports.map((r) => {
                  const s = r.tiers[tier];
                  const v = s ? pick(s)[k] : undefined;
                  return (
                    <td key={r.extractor} className="mono text-center tabular" style={heat(v, goodHigh)}>
                      {v === undefined ? <span className="text-faint">n/a</span> : pct(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function FlagCompare({ raised, expected }: { raised: string[]; expected: string[] }) {
  const all = Array.from(new Set([...expected, ...raised]));
  if (!all.length) return <span className="text-faint">–</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {all.map((c) => {
        const e = expected.includes(c);
        const r = raised.includes(c);
        const tone = e && r ? "ok" : e ? "bad" : isDefect(c) ? "warn" : "neutral";
        const t = e && r ? "caught" : e ? "MISSED" : isDefect(c) ? "false alarm" : "process flag";
        return (
          <Badge key={c} mono tone={tone} title={t}>
            {e && !r ? "✗ " : ""}
            {c}
          </Badge>
        );
      })}
    </span>
  );
}

function CaseTable({ report, tier }: { report: EvalReport; tier: Tier }) {
  const rows = report.cases[tier] ?? [];
  const { spec, second, reader } = parseName(report.extractor);
  const [only, setOnly] = useState<"all" | "wrong">("all");
  const isWrong = (r: CaseScore | CaseError) => {
    if ("error" in r && r.error) return true;
    const s = r as CaseScore;
    const exp = s.expected.length > 0;
    return exp !== (s.decision === "manual_review") || s.expected.some((e) => !s.raised.includes(e)) || s.raised.some((x) => isDefect(x) && !s.expected.includes(x));
  };
  const shown = only === "all" ? rows : rows.filter(isWrong);
  return (
    <Section
      title={`Per case · ${report.extractor} · ${tier}`}
      pad={false}
      right={
        <span className="flex items-center gap-2">
          <span className="text-[11px] text-muted">click a row to open it in the Pipeline</span>
          <Tabs size="sm" value={only} onChange={setOnly} tabs={[{ id: "all", label: `all ${rows.length}` }, { id: "wrong", label: `wrong ${rows.filter(isWrong).length}` }]} />
        </span>
      }
    >
      <div className="overflow-x-auto">
        <table className="dt text-[12px]">
          <thead>
            <tr>
              <th>case</th>
              <th>defects</th>
              <th>traps</th>
              <th>decision</th>
              <th>flags (expected vs raised)</th>
              <th>fields</th>
              <th>s</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              if ("error" in r && r.error)
                return (
                  <tr key={r.case}>
                    <td className="mono">{r.case}</td>
                    <td colSpan={6} className="mono text-bad">
                      {r.error}
                    </td>
                  </tr>
                );
              const s = r as CaseScore;
              const f = Object.values(s.fields);
              const ok = f.filter((x) => x.ok).length;
              const missed = s.expected.length > 0 && s.decision === "pre_filled_review";
              return (
                <tr
                  key={s.case}
                  className={cx("cursor-pointer hover:bg-sunk", missed && "bg-bad-weak")}
                  onClick={() => navigate("pipeline", { tier, case: s.case, extractor: spec, second, reader })}
                >
                  <td className="mono font-medium">{s.case}</td>
                  <td>
                    <span className="flex flex-wrap gap-1">
                      {s.defects.map((d) => (
                        <Badge key={d} mono tone="bad" title={DEFECTS[d]}>
                          {d}
                        </Badge>
                      ))}
                    </span>
                  </td>
                  <td>
                    <span className="flex flex-wrap gap-1">
                      {s.traps.map((d) => (
                        <Badge key={d} mono tone="warn" title={TRAPS[d]}>
                          {d}
                        </Badge>
                      ))}
                    </span>
                  </td>
                  <td>
                    <DecisionBadge decision={s.decision} />
                  </td>
                  <td>
                    <FlagCompare raised={s.raised} expected={s.expected} />
                  </td>
                  <td className={cx("mono tabular", ok < f.length && "text-warn")}>
                    {ok}/{f.length}
                  </td>
                  <td className="mono tabular text-muted">{s.totals?.seconds ?? "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

export function EvalsPage({ route }: { route: Route }) {
  const evals = useFetch<EvalReport[]>("evals", api.evals, false);
  const tier = (TIERS.includes(route.params.tier as Tier) ? route.params.tier : "scan") as Tier;
  const suite = (route.params.suite === "hard" ? "hard" : "standard") as Suite;
  useEffect(() => {
    const i = window.setInterval(() => evals.reload(), 60000);
    return () => window.clearInterval(i);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const reports = useMemo(
    () => (evals.data ?? []).filter((r) => (r.suite ?? "standard") === suite && r.tiers[tier] && Object.keys(r.tiers[tier]!).length),
    [evals.data, tier, suite],
  );
  const chosen = route.params.ex && reports.find((r) => r.extractor === route.params.ex) ? route.params.ex : reports[0]?.extractor;
  const chosenReport = reports.find((r) => r.extractor === chosen);

  const union = (pick: (s: Summary) => Record<string, unknown>) =>
    Array.from(new Set(reports.flatMap((r) => Object.keys(pick(r.tiers[tier]!) ?? {})))).sort();

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-auto">
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-panel px-4 py-2.5">
        <Tabs
          tabs={[
            { id: "standard" as Suite, label: "standard suite", title: "case_NNN: shows the system working" },
            { id: "hard" as Suite, label: "hard suite", title: "hard_NNN: built to break it" },
          ]}
          value={suite}
          onChange={(v) => setParams({ suite: v, ex: null }, false)}
        />
        <Tabs tabs={TIERS.map((t) => ({ id: t, label: t }))} value={tier} onChange={(t) => setParams({ tier: t }, false)} />
        <span className="text-[12px] text-muted">
          {suite === "hard"
            ? "Defects inside traps, thresholds at their edge, one-digit changes, new injection wordings, Form A cases the standard suite lacks, and two held-out cases expected to fail."
            : TIER_INFO[tier]}
        </span>
        <span className="ml-auto text-[12px] text-muted">
          {evals.data ? `${evals.data.length} eval report(s)` : ""} · refreshes every 60 s
        </span>
        <button className="h-7 rounded-md border border-line px-2 text-[12px] hover:bg-sunk" onClick={evals.reload}>
          {evals.loading ? <Spinner /> : "refresh"}
        </button>
      </div>
      <div className="flex flex-col gap-3 p-4">
        {evals.error && <ErrorBox>{evals.error}</ErrorBox>}
        {evals.data && reports.length === 0 && (
          <Empty>
            No {suite} eval reports for this tier yet{suite === "hard" ? ": python -m kyc_demo eval --suite hard -e <extractor>" : ""}.
          </Empty>
        )}
        {reports.length > 0 && (
          <>
            <Section title={`Metrics · ${tier} · ${reports[0].tiers[tier]!.files} files`} pad={false}>
              <div className="overflow-x-auto">
                <table className="dt text-[12.5px]">
                  <thead>
                    <tr>
                      <th>metric</th>
                      {reports.map((r) => (
                        <th key={r.extractor} className="mono normal-case tracking-normal" title={r.extractor}>
                          {short(r.extractor)}
                          <div className="font-normal text-faint">as of {r.as_of}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {METRICS.map((m) => {
                      const vals = reports.map((r) => r.tiers[tier]![m.key] as number | null);
                      const nums = vals.filter((v): v is number => v !== null && v !== undefined);
                      const best = nums.length > 1 ? (m.better === "high" ? Math.max(...nums) : Math.min(...nums)) : null;
                      return (
                        <tr key={m.key}>
                          <td className="w-[360px] min-w-[300px]">
                            <div className="font-medium">
                              {m.label}
                              <span className="ml-1 text-[10px] text-faint">{m.better === "high" ? "higher is better" : "lower is better"}</span>
                            </div>
                            <div className="text-[11.5px] text-muted">{m.legend}</div>
                          </td>
                          {vals.map((v, i) => (
                            <td key={i} className={cx("mono tabular", v === best && "bg-accent-weak font-semibold text-accent")}>
                              {fmt(v, m.kind)}
                              {m.key === "defect_recall" && reports[i].tiers[tier]!.defect_recall_ci && (
                                <span className="font-normal text-faint">
                                  {" "}
                                  ({pct(reports[i].tiers[tier]!.defect_recall_ci![0])}–{pct(reports[i].tiers[tier]!.defect_recall_ci![1])})
                                </span>
                              )}
                              {m.key === "missed_defect_files" && v !== null && (
                                <span className="font-normal text-faint"> / {reports[i].tiers[tier]!.defect_files}</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Section>
            <div className="grid gap-3">
              <Grid title="Recall per defect (higher is better)" rows={union((s) => s.per_defect)} reports={reports} tier={tier} pick={(s) => s.per_defect} goodHigh explain={DEFECTS} />
              <Grid title="False-alarm rate per trap (lower is better)" rows={union((s) => s.per_trap)} reports={reports} tier={tier} pick={(s) => s.per_trap} goodHigh={false} explain={TRAPS} />
            </div>
            <Grid title="Accuracy per field" rows={union((s) => s.fields)} reports={reports} tier={tier} pick={(s) => s.fields} goodHigh />
            <div className="flex items-center gap-2">
              <span className="text-[12px] text-muted">Per-case results for</span>
              <select
                className="mono h-7 rounded-md border border-line bg-panel px-2 text-[12px]"
                value={chosen}
                onChange={(e) => setParams({ ex: e.target.value }, true)}
              >
                {reports.map((r) => (
                  <option key={r.extractor}>{r.extractor}</option>
                ))}
              </select>
            </div>
            {chosenReport && <CaseTable report={chosenReport} tier={tier} />}
          </>
        )}
        {!evals.data && evals.loading && (
          <div className="flex items-center gap-2 text-muted">
            <Spinner /> loading evals
          </div>
        )}
      </div>
    </div>
  );
}
