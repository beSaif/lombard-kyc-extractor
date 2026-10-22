import { DEFECTS, DOC_LABEL, PROCESS_FLAGS, TRAPS, cx, isDefect, num } from "../lib";
import type { Result } from "../types";
import { Badge, PassMark, Section, StatusBadge } from "../ui";
import { DecisionBadge, FlagList } from "./ChecksView";

/** An uploaded file has no truth.json: show what the pipeline decided and why, and point to Review. */
function UploadSummary({ result }: { result: Result }) {
  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-[16px] font-semibold">Run summary</h2>
        <Badge mono>{result.run_id}</Badge>
        <Badge mono tone="accent">
          {result.extractor}
        </Badge>
        <Badge>review date {result.as_of}</Badge>
      </header>
      <Section title="Decision">
        <DecisionBadge decision={result.decision} big />
        <div className="mt-2 text-[12px] text-muted">
          Your own documents: there is no truth to score against. Open <b>Review</b> to check each value against the page and sign off.
        </div>
      </Section>
      <Section title="Flags raised (reasons for manual review)" pad={false}>
        <div className="p-2">
          <FlagList flags={result.flags} />
        </div>
      </Section>
    </div>
  );
}

export function SummaryView({ result }: { result: Result }) {
  if (!result.score) return <UploadSummary result={result} />;
  const s = result.score;
  const expected = new Set(s?.expected ?? []);
  const raised = new Set(s?.raised ?? result.flags.map((f) => f.code));
  const expDecision = expected.size ? "manual_review" : "pre_filled_review";
  const codes = Array.from(new Set([...expected, ...raised]));
  const routingOk = result.decision === expDecision;
  const missedFile = expected.size > 0 && result.decision === "pre_filled_review";
  const fields = Object.entries(s?.fields ?? {});
  const okCount = fields.filter(([, f]) => f.ok).length;
  const t = result.totals;
  const isLocal = result.extractor.startsWith("ollama") || result.extractor === "rules";

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-[16px] font-semibold">Run summary</h2>
        <Badge mono>{result.run_id}</Badge>
        <Badge mono>
          {result.tier}/{result.case}
        </Badge>
        <Badge mono tone="accent">
          {result.extractor}
        </Badge>
        {result.second && <Badge mono tone="info">+ {result.second}</Badge>}
        <Badge>reader {result.reader}</Badge>
        <Badge>review date {result.as_of}</Badge>
      </header>

      <div className="grid gap-3 @3xl:grid-cols-2">
        <Section title="Decision vs ground truth">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-faint">pipeline decided</div>
              <DecisionBadge decision={result.decision} big />
            </div>
            <div className="text-faint">vs</div>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-faint">expected (from truth.json)</div>
              <DecisionBadge decision={expDecision} big />
            </div>
          </div>
          <div
            className={cx(
              "mt-3 rounded px-3 py-2 text-[12px] font-medium",
              missedFile ? "bg-bad-weak text-bad" : routingOk ? "bg-ok-weak text-ok" : "bg-warn-weak text-warn",
            )}
          >
            {missedFile
              ? "Missed defect: a file with a real problem skipped manual review. This is the dangerous error."
              : routingOk
                ? "Routed correctly."
                : "Clean file sent to manual review: costs reviewer time, not safety."}
          </div>
        </Section>
        <Section title="Flags: expected vs raised">
          <table className="dt text-[12px]">
            <thead>
              <tr>
                <th>code</th>
                <th>expected</th>
                <th>raised</th>
                <th>verdict</th>
              </tr>
            </thead>
            <tbody>
              {codes.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-faint">
                    No flags expected, none raised.
                  </td>
                </tr>
              )}
              {codes.map((c) => {
                const e = expected.has(c);
                const r = raised.has(c);
                const verdict = e && r ? "caught" : e ? "MISSED" : isDefect(c) ? "false alarm" : "process flag";
                return (
                  <tr key={c} className={cx(e && !r && "bg-bad-weak", !e && r && isDefect(c) && "bg-warn-weak")}>
                    <td className="mono" title={DEFECTS[c] ?? PROCESS_FLAGS[c]}>
                      {c}
                    </td>
                    <td>{e ? "●" : <span className="text-faint">–</span>}</td>
                    <td>{r ? "●" : <span className="text-faint">–</span>}</td>
                    <td className={cx(verdict === "caught" && "text-ok", verdict === "MISSED" && "font-semibold text-bad", verdict === "false alarm" && "text-warn", verdict === "process flag" && "text-muted")}>
                      {verdict}
                      {verdict === "process flag" && <div className="text-[11px] text-faint">{PROCESS_FLAGS[c]}</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      </div>

      {(s?.defects?.length || s?.traps?.length) && (
        <Section title="What this case contains">
          <div className="flex flex-col gap-1 text-[12px]">
            {s.defects.map((d) => (
              <div key={d} className="flex gap-2">
                <Badge mono tone="bad">
                  {d}
                </Badge>
                <span className="text-muted">{DEFECTS[d]}</span>
              </div>
            ))}
            {s.traps.map((d) => (
              <div key={d} className="flex gap-2">
                <Badge mono tone="warn">
                  {d}
                </Badge>
                <span className="text-muted">{TRAPS[d]} (harmless; must not be flagged)</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Flags raised (reasons for manual review)" pad={false}>
        <div className="p-2">
          <FlagList flags={result.flags} />
        </div>
      </Section>

      <Section
        title="Fields: extracted vs truth"
        pad={false}
        right={
          <span className="text-[11px] text-muted">
            {okCount}/{fields.length} correct (normalised comparison)
          </span>
        }
      >
        <div className="overflow-x-auto">
          <table className="dt text-[12px]">
            <thead>
              <tr>
                <th>doc</th>
                <th>field</th>
                <th>extracted</th>
                <th>truth</th>
                <th>ok</th>
                <th>final evidence</th>
              </tr>
            </thead>
            <tbody>
              {fields.map(([k, f]) => {
                const [doc, name] = k.split(".");
                const ev = result.evidence?.[doc as keyof typeof result.evidence]?.[name]?.status;
                return (
                  <tr key={k} className={cx(!f.ok && "bg-bad-weak")}>
                    <td className="whitespace-nowrap text-muted">{DOC_LABEL[doc] ?? doc}</td>
                    <td className="mono">{name}</td>
                    <td className="mono break-all">{f.got ?? <span className="text-faint">null</span>}</td>
                    <td className={cx("mono break-all", f.got === f.want ? "text-faint" : "text-muted")}>{f.want ?? "null"}</td>
                    <td>
                      <PassMark passed={f.ok} size={11} />
                    </td>
                    <td>{ev ? <StatusBadge status={ev} /> : <span className="text-faint">–</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Totals">
        <div className="grid grid-cols-2 gap-2 @2xl:grid-cols-5">
          {[
            ["wall time", `${t.seconds} s`],
            ["model time", `${t.model_seconds} s`],
            ["input tokens", num(t.input_tokens)],
            ["output tokens", num(t.output_tokens)],
            ["cost", isLocal && !t.cost_usd ? "free (local)" : t.cost_usd != null ? `$${t.cost_usd.toFixed(5)}` : "–"],
          ].map(([k, v]) => (
            <div key={k} className="rounded border border-line bg-sunk px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-faint">{k}</div>
              <div className="mono text-[15px] tabular">{v}</div>
            </div>
          ))}
        </div>
        {Object.keys(result.usage ?? {}).length > 0 && (
          <table className="dt mt-2 text-[12px]">
            <thead>
              <tr>
                <th>usage</th>
                <th>input</th>
                <th>output</th>
                <th>reasoning</th>
                <th>seconds</th>
                <th>cost</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.usage).map(([k, u]) => (
                <tr key={k}>
                  <td className="mono">{k}</td>
                  <td className="mono tabular">{num(u?.input_tokens)}</td>
                  <td className="mono tabular">{num(u?.output_tokens)}</td>
                  <td className="mono tabular">{num(u?.reasoning_tokens)}</td>
                  <td className="mono tabular">{u?.seconds ?? "–"}</td>
                  <td className="mono tabular">{u?.cost_usd != null ? `$${u.cost_usd.toFixed(5)}` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  );
}
