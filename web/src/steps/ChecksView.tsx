import { useState } from "react";
import { DOC_LABEL, PROCESS_FLAGS, STATUS_COLOR, cx, isDefect } from "../lib";
import type { Check, Flag, Step } from "../types";
import { Badge, JsonBox, PassMark, Section, StatusBadge } from "../ui";
import { MrzRuler } from "./ReadView";

const sevTone = (s: string) => (s === "high" ? "bad" : s === "medium" ? "warn" : "neutral") as "bad" | "warn" | "neutral";

function CheckInputs({ c }: { c: Check }) {
  const i = c.inputs ?? {};
  if (c.name === "passport.mrz_check_digits" && i.checks) {
    return (
      <div className="flex flex-col gap-2">
        <table className="dt w-auto text-[12px]">
          <thead>
            <tr>
              <th>check digit over</th>
              <th>ok</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(i.checks as Record<string, boolean | null>).map(([k, v]) => (
              <tr key={k}>
                <td className="mono">{k}</td>
                <td>
                  <PassMark passed={v} size={11} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {i.line1 !== undefined && <MrzRuler lines={[i.line1, i.line2]} />}
      </div>
    );
  }
  if (c.name === "passport.mrz_vs_visual" && i.printed && i.mrz) {
    const keys = Array.from(new Set([...Object.keys(i.printed), ...Object.keys(i.mrz)]));
    return (
      <table className="dt w-auto text-[12px]">
        <thead>
          <tr>
            <th>field</th>
            <th>printed page</th>
            <th>MRZ</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const same = String(i.printed[k] ?? "") === String(i.mrz[k] ?? "");
            return (
              <tr key={k} className={cx(!same && "bg-bad-weak")}>
                <td className="mono">{k}</td>
                <td className="mono">{String(i.printed[k] ?? "–")}</td>
                <td className="mono">{String(i.mrz[k] ?? "–")}</td>
                <td>{same ? <span className="text-ok">=</span> : <span className="text-bad">≠</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
  if ("a" in i && "b" in i) {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2">
          <div className="rounded border border-line bg-sunk p-2">
            <div className="text-[10px] uppercase tracking-wider text-faint">a</div>
            <div className="mono break-words">{String(i.a ?? "null")}</div>
          </div>
          <div className={cx("self-center text-lg", c.passed ? "text-ok" : c.passed === false ? "text-bad" : "text-faint")}>
            {c.passed ? "≈" : c.passed === false ? "≠" : "?"}
          </div>
          <div className="rounded border border-line bg-sunk p-2">
            <div className="text-[10px] uppercase tracking-wider text-faint">b</div>
            <div className="mono break-words">{String(i.b ?? "null")}</div>
          </div>
        </div>
        {i.rule && (
          <div className="text-[11px] text-muted">
            rule: <span className="text-fg">{i.rule}</span>
          </div>
        )}
      </div>
    );
  }
  if (c.name.endsWith(".cross_model") && i.fields) return <CrossTable fields={i.fields} />;
  return <JsonBox value={i} open={3} maxH={260} />;
}

export function CheckRow({ c }: { c: Check }) {
  const [open, setOpen] = useState(c.passed === false);
  return (
    <div className={cx("border-b border-line last:border-b-0", c.passed === false && "bg-bad-weak/40")}>
      <button className="flex w-full items-start gap-2 px-3 py-1.5 text-left hover:bg-sunk" onClick={() => setOpen(!open)}>
        <span className="pt-0.5">
          <PassMark passed={c.passed} size={11} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{c.label}</span>
            <span className="mono text-[11px] text-faint">{c.name}</span>
            {c.passed === false && (
              <Badge mono tone={sevTone(c.severity)}>
                {c.flag}
              </Badge>
            )}
          </span>
          <span className="block text-[12px] text-muted">{c.detail}</span>
        </span>
        <span className="pt-0.5 text-[11px] text-faint">{open ? "▾ inputs" : "▸ inputs"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 pl-9">
          <CheckInputs c={c} />
        </div>
      )}
    </div>
  );
}

function groupOf(c: Check): string {
  if (c.name.startsWith("cross.")) return "Cross-document";
  if (/^passport\.(mrz|not_expired)/.test(c.name)) return "Passport";
  return "Per-document";
}

export function ChecksList({ checks, grouped = true }: { checks: Check[]; grouped?: boolean }) {
  if (!grouped)
    return (
      <div className="rounded-md border border-line bg-panel">
        {checks.map((c) => (
          <CheckRow key={c.name} c={c} />
        ))}
      </div>
    );
  const groups = ["Passport", "Cross-document", "Per-document"];
  return (
    <div className="flex flex-col gap-3">
      {groups.map((g) => {
        const cs = checks.filter((c) => groupOf(c) === g);
        if (!cs.length) return null;
        const failed = cs.filter((c) => c.passed === false).length;
        return (
          <Section
            key={g}
            title={g}
            pad={false}
            right={
              <span className="text-[11px] text-muted">
                {cs.length} checks · <span className={failed ? "text-bad" : "text-ok"}>{failed} failed</span>
              </span>
            }
          >
            {cs.map((c) => (
              <CheckRow key={c.name} c={c} />
            ))}
          </Section>
        );
      })}
    </div>
  );
}

export function ValidateView({ step }: { step: Step }) {
  const checks: Check[] = step.data.checks ?? [];
  const pass = checks.filter((c) => c.passed === true).length;
  const fail = checks.filter((c) => c.passed === false).length;
  const skip = checks.length - pass - fail;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <Badge tone="ok">{pass} passed</Badge>
        <Badge tone={fail ? "bad" : "neutral"}>{fail} failed</Badge>
        <Badge>{skip} skipped</Badge>
        <span className="text-[12px] text-muted">Click a row to see the exact inputs the rule saw.</span>
      </div>
      <ChecksList checks={checks} />
    </div>
  );
}

function CrossTable({ fields }: { fields: Record<string, { primary: string | null; second: string | null; agree: boolean }> }) {
  return (
    <table className="dt text-[12px]">
      <thead>
        <tr>
          <th>field</th>
          <th>primary model</th>
          <th>second model</th>
          <th>agree</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(fields).map(([f, r]) => (
          <tr key={f} className={cx(!r.agree && "bg-bad-weak")}>
            <td className="mono">{f}</td>
            <td className="mono break-all">{r.primary ?? <span className="text-faint">null</span>}</td>
            <td className="mono break-all">{r.second ?? <span className="text-faint">null</span>}</td>
            <td>
              <PassMark passed={r.agree} size={11} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CrossModelView({ step }: { step: Step }) {
  const c: Check | undefined = step.data.check;
  if (!c) return null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <PassMark passed={c.passed} />
        <span className="font-medium">{c.label}</span>
        <span className="text-muted">{c.detail}</span>
        {c.passed === false && (
          <Badge mono tone="warn">
            {c.flag}
          </Badge>
        )}
      </div>
      <div className="rounded-md border border-line bg-panel">
        <CrossTable fields={c.inputs?.fields ?? {}} />
      </div>
      <p className="text-[11px] text-muted">Values are compared after normalisation (same() in normalise.py): names token-wise, addresses by key, dates as ISO.</p>
    </div>
  );
}

export function StatusMatrix({ status }: { status: Record<string, Record<string, string>> }) {
  return (
    <div className="flex flex-col gap-2">
      {Object.entries(status).map(([doc, fields]) => (
        <div key={doc} className="flex flex-wrap items-center gap-1">
          <span className="w-32 shrink-0 text-[12px] text-muted">{DOC_LABEL[doc] ?? doc}</span>
          {Object.entries(fields).map(([f, s]) => (
            <span
              key={f}
              title={`${doc}.${f}: ${s}`}
              className="mono rounded px-1.5 py-0.5 text-[11px] text-white"
              style={{ background: STATUS_COLOR[s] ?? "var(--faint)" }}
            >
              {f}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

export function CorroborateView({ step }: { step: Step }) {
  const d = step.data;
  const log: { field: string; by: string; value: string }[] = d.corroborated ?? [];
  return (
    <div className="flex flex-col gap-3">
      <Section title={`Corroboration chains (${log.length})`}>
        {log.length === 0 ? (
          <div className="text-[12px] text-faint">Nothing needed corroborating, or no passing check could vouch for an unverified value.</div>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {log.map((l, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="mono rounded bg-warn-weak px-1.5 text-warn">{l.field}</span>
                <span className="text-faint">←</span>
                <span className="mono rounded bg-ok-weak px-1.5 text-ok">{l.by}</span>
                <span className="text-faint">⇒</span>
                <StatusBadge status="corroborated" />
                <span className="mono text-muted">“{l.value}”</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[11px] text-muted">
          An unverified value (not found on the page, often handwriting) becomes <b>corroborated</b> when a passing cross-document check ties it to a
          verified value on another document.
        </p>
      </Section>
      <Section title="Final evidence status per field">
        <StatusMatrix status={d.status ?? {}} />
      </Section>
      <ChecksList checks={d.checks ?? []} grouped={false} />
    </div>
  );
}

export function DecisionBadge({ decision, big = false }: { decision: string; big?: boolean }) {
  const ok = decision === "pre_filled_review";
  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 rounded-md border font-semibold",
        big ? "px-4 py-2 text-[16px]" : "px-1.5 py-[1px] text-[11px]",
        ok ? "border-ok/30 bg-ok-weak text-ok" : "border-bad/30 bg-bad-weak text-bad",
      )}
    >
      {ok ? "● pre-filled review" : "● manual review"}
    </span>
  );
}

export function FlagList({ flags }: { flags: Flag[] }) {
  if (!flags.length) return <div className="text-[12px] text-faint">No flags.</div>;
  return (
    <ul className="flex flex-col divide-y divide-line rounded-md border border-line bg-panel">
      {flags.map((f, i) => (
        <li key={i} className="flex items-start gap-2 px-3 py-2">
          <Badge mono tone={sevTone(f.severity)}>
            {f.code}
          </Badge>
          <Badge>{f.severity}</Badge>
          {!isDefect(f.code) && <Badge tone="neutral">process flag</Badge>}
          <span className="flex-1 text-[12px]">{f.message}</span>
          <span className="mono text-[11px] text-faint">{f.check}</span>
        </li>
      ))}
    </ul>
  );
}

export function RouteView({ step }: { step: Step }) {
  const d = step.data;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-4">
        <DecisionBadge decision={d.decision} big />
        <span className="text-[12px] text-muted">
          {d.decision === "pre_filled_review"
            ? "No check failed: the file goes to the quick queue, fields pre-filled."
            : `${(d.flags ?? []).length} failed check(s): the file goes to the manual queue with these reasons.`}
        </span>
      </div>
      <FlagList flags={d.flags ?? []} />
      <div className="text-[11px] text-muted">
        Rule: <span className="mono">decision = "manual_review" if flags else "pre_filled_review"</span>. Process flags (e.g.{" "}
        {Object.keys(PROCESS_FLAGS).join(", ")}) route to manual review but are not counted as defects in evals.
      </div>
    </div>
  );
}

export function MrzReconcileView({ step }: { step: Step }) {
  const d = step.data;
  const cands: Record<string, (string | null)[]> = d.candidates ?? {};
  const valid: Record<string, boolean> = d.valid ?? {};
  const hasLines = Array.isArray(d.lines) && d.lines.some(Boolean);
  const won = (lines: (string | null)[]) => hasLines && lines && lines[0] === d.lines[0] && lines[1] === d.lines[1];
  const winner = Object.keys(cands).find((k) => valid[k] && won(cands[k])) ?? Object.keys(cands).find((k) => won(cands[k]));
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded border-l-2 border-accent bg-accent-weak px-3 py-1.5 text-[12px]">
        LLMs miscount runs of '&lt;' (tokenisation merges them) and OCR reads '&lt;' as K, E or S, so the MRZ is taken from
        whichever reading passes its checksums. Line 1 has no check digit, so its tail is cleaned structurally: no name
        contains '&lt;&lt;&lt;'.
      </div>
      <div className="overflow-x-auto rounded-md border border-line bg-panel">
        <table className="dt text-[12px]">
          <thead>
            <tr>
              <th>candidate</th>
              <th>line 1</th>
              <th>line 2</th>
              <th>check digits</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(cands).map(([k, lines]) => (
              <tr key={k} className={cx(k === winner && "bg-ok-weak")}>
                <td className="whitespace-nowrap">
                  <span className="mono">{k}</span>
                  {k === winner && (
                    <Badge tone="ok" className="ml-1">
                      used
                    </Badge>
                  )}
                </td>
                {[0, 1].map((li) => {
                  const l = lines?.[li] ?? null;
                  return (
                    <td key={li} className="mono">
                      {l === null ? (
                        <span className="text-faint">null</span>
                      ) : (
                        <>
                          <div className="break-all">{l}</div>
                          <div className={cx("text-[10px]", l.length === 44 ? "text-faint" : "text-bad font-semibold")}>{l.length} chars</div>
                        </>
                      )}
                    </td>
                  );
                })}
                <td>
                  <PassMark passed={lines?.[0] == null ? null : valid[k]} size={11} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-line px-3 py-1.5 text-[11px] text-muted">
          source: <span className="text-fg">{d.source}</span>
        </div>
      </div>
      {!hasLines && <div className="text-[12px] text-muted">No candidate produced two MRZ lines (the extractor returned null), so the MRZ fields stay empty.</div>}
      {hasLines && (
        <Section title="Chosen MRZ">
          <MrzRuler lines={d.lines} compare={cands.model} />
          <div className="text-[11px] text-faint">Red underlined characters differ from the model's raw reading.</div>
        </Section>
      )}
    </div>
  );
}
