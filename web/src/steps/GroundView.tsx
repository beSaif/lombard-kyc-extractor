import { useState } from "react";
import { Figure } from "../Figure";
import { BASIS_INFO, STATUS_COLOR, cx } from "../lib";
import type { Evidence, Result, Step } from "../types";
import { Badge, Bar, StatusBadge, Tabs } from "../ui";

const THRESHOLD = 85;

export function GroundView({ step, steps, result }: { step: Step; steps: Step[]; result?: Result }) {
  const evidence: Record<string, Evidence> = step.data.evidence ?? {};
  const fields: Record<string, { value: string | null; quote: string | null; page: number | null }> = step.data.fields ?? {};
  const final = result && step.doc ? result.evidence?.[step.doc] : undefined;
  const reads = steps.filter((s) => s.kind === "read" && s.doc === step.doc && s.id < step.id);
  const pages = Array.from(new Set(reads.map((r) => r.data.page as number)));
  const [page, setPage] = useState<number>(pages[0] ?? 1);
  const read = reads.find((r) => r.data.page === page) ?? reads[reads.length - 1];
  const [hover, setHover] = useState<string | null>(null);
  const [useFinal, setUseFinal] = useState<"ground" | "final">(final ? "final" : "ground");
  const statusOf = (f: string) => (useFinal === "final" && final?.[f] ? final[f].status : evidence[f]?.status);

  const names = Object.keys(evidence);
  const overlay = (
    <>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
        {names.map((f) => {
          const e = evidence[f];
          if (!e.bbox || (e.page ?? 1) !== page) return null;
          const [x0, y0, x1, y1] = e.bbox;
          const col = STATUS_COLOR[statusOf(f)] ?? "var(--faint)";
          const lit = hover === f;
          return (
            <rect
              key={f}
              x={x0 - 0.003}
              y={y0 - 0.003}
              width={x1 - x0 + 0.006}
              height={y1 - y0 + 0.006}
              fill={col}
              fillOpacity={lit ? 0.3 : 0.08}
              stroke={col}
              strokeWidth={lit ? 3 : 1.5}
              strokeDasharray={e.method === "not_found" ? "4 3" : undefined}
              vectorEffect="non-scaling-stroke"
              onMouseEnter={() => setHover(f)}
              onMouseLeave={() => setHover(null)}
            />
          );
        })}
      </svg>
      {names.map((f) => {
        const e = evidence[f];
        if (!e.bbox || (e.page ?? 1) !== page) return null;
        const lit = hover === f;
        return (
          <div
            key={f}
            className={cx("pointer-events-none absolute mono rounded-sm px-1 text-[9px] leading-[13px] whitespace-nowrap text-white", lit ? "z-20" : "z-10 opacity-85")}
            style={{ left: `${e.bbox[0] * 100}%`, top: `calc(${e.bbox[1] * 100}% - 14px)`, background: STATUS_COLOR[statusOf(f)] ?? "gray" }}
          >
            {f}
            {lit && e.score !== null ? ` · ${e.score}` : ""}
          </div>
        );
      })}
    </>
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <span className="text-muted">Box colour:</span>
        {(["verified", "corroborated", "unverified", "dropped", "out_of_place"] as const).map((s) => (
          <span key={s} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: STATUS_COLOR[s] }} />
            {s}
          </span>
        ))}
        <span className="text-faint">· dashed = best guess, not a match (score &lt; {THRESHOLD})</span>
        <span className="ml-auto flex items-center gap-2">
          {pages.length > 1 && (
            <Tabs size="sm" tabs={pages.map((p) => ({ id: String(p), label: `p${p}` }))} value={String(page)} onChange={(v) => setPage(+v)} />
          )}
          {final && (
            <Tabs
              size="sm"
              tabs={[
                { id: "ground", label: "status at grounding", title: "evidence.status as computed in this step" },
                { id: "final", label: "final (after corroboration)", title: "result.evidence" },
              ]}
              value={useFinal}
              onChange={setUseFinal}
            />
          )}
        </span>
      </div>
      <Figure src={read?.data.image} overlay={overlay} caption={`Evidence boxes on the ${read?.data.source === "text_layer" ? "text-layer" : "OCR"} page image (same coordinates as the read step).`} />
      <div className="overflow-x-auto rounded-md border border-line bg-panel">
        <table className="dt text-[12px]">
          <thead>
            <tr>
              <th>field</th>
              <th>value</th>
              <th>model's quote → matched on page</th>
              <th>method</th>
              <th>score</th>
              <th>status</th>
              <th>why / corroborated by</th>
            </tr>
          </thead>
          <tbody>
            {names.map((f) => {
              const e = evidence[f];
              const fin = final?.[f];
              const changed = fin && fin.status !== e.status;
              return (
                <tr
                  key={f}
                  onMouseEnter={() => setHover(f)}
                  onMouseLeave={() => setHover(null)}
                  className={cx(hover === f && "bg-accent-weak")}
                >
                  <td className="mono whitespace-nowrap">{f}</td>
                  <td className="mono min-w-[110px] break-words">{e.value ?? <span className="text-faint">null</span>}</td>
                  <td className="mono min-w-[140px] break-words text-[11.5px]">
                    <div className="text-muted">
                      <span className="text-faint">q </span>
                      {fields[f]?.quote ?? <span className="text-faint">null</span>}
                    </div>
                    <div className={e.method === "not_found" ? "text-warn" : "text-ok"}>
                      <span className="text-faint">p </span>
                      {e.matched_text ?? <span className="text-faint">–</span>}
                    </div>
                  </td>
                  <td>
                    <Badge mono tone={e.method === "not_found" ? "warn" : e.method === "exact" || e.method === "checksum" ? "ok" : "info"}>
                      {e.method}
                    </Badge>
                    {e.basis && (
                      <div className="mt-0.5 text-[10.5px] text-faint" title={BASIS_INFO[e.basis]}>
                        basis: {e.basis}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-1.5 whitespace-nowrap">
                      <Bar value={e.score} threshold={THRESHOLD} color={e.score !== null && e.score >= THRESHOLD ? "var(--ok)" : "var(--warn)"} />
                      <span className="mono tabular text-[11px]">{e.score ?? "–"}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap">
                    <StatusBadge status={e.status} />
                    {changed && (
                      <>
                        <span className="mx-1 text-faint">→</span>
                        <StatusBadge status={fin!.status} />
                      </>
                    )}
                  </td>
                  <td className="text-[11px] text-muted">
                    {e.why && <div>{e.why}</div>}
                    {e.place && e.place.verdict !== "no_label" && e.status !== "out_of_place" && (
                      <div className="text-faint">
                        {e.place.verdict === "anchored" ? <>under its label <span className="mono">{e.place.label}</span></> : e.place.verdict}
                      </div>
                    )}
                    {(fin?.corroborated_by ?? e.corroborated_by) && (
                      <div className="text-info">
                        corroborated by <span className="mono">{fin?.corroborated_by ?? e.corroborated_by}</span>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted">
        Two tests per value. Does its own quote say it? A quote that says something else (another name, date or number) gets the value{" "}
        <b>dropped</b>; one that is only close (OCR noise copied into the quote) leaves it <b>unverified</b>. Is the quote on the page? Score = fuzzy
        match (0–100) against the OCR words, ≥ {THRESHOLD} counts as found, but digits must match exactly: one digit off is another house or date,
        not noise. Is the quote where that field is printed? One in fine print, or under another field&apos;s label or a remarks box, is{" "}
        <b>out_of_place</b>: a person must look, and no other document can vouch for it, since a planted decoy is made to agree with them.
        Unverified values wait for a passing cross-document check to corroborate them, or for a person. <b>basis</b> says what a
        verification rests on: in text/both mode the model was shown the OCR, so <span className="mono">ocr</span> means it agrees with OCR, not
        that two readers did; <span className="mono">checksum</span> (the MRZ) is the only check neither can fake.
      </p>
    </div>
  );
}
