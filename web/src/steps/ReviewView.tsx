import { useEffect, useState } from "react";
import { api, lsGet, lsSet } from "../api";
import { Figure } from "../Figure";
import { BASIS_INFO, DOCS, DOC_LABEL, STATUS_COLOR, cx } from "../lib";
import type { AuditEntry, DocType, Evidence, Result, ReviewState, ReviewStatus, Step } from "../types";
import { Badge, ErrorBox, Section, Spinner, StatusBadge } from "../ui";
import { DecisionBadge, FlagList } from "./ChecksView";

const LS_REVIEWER = "kyc.reviewer";

const STATUS_LABEL: Record<ReviewStatus, [string, "neutral" | "info" | "ok" | "bad" | "warn"]> = {
  open: ["open: nobody has signed off", "neutral"],
  awaiting_second_approval: ["approved once: waiting for a second reviewer", "info"],
  approved: ["approved by two reviewers", "ok"],
  rejected: ["rejected", "bad"],
  info_requested: ["more information requested from the client", "warn"],
};

export function ReviewBadge({ status }: { status: ReviewStatus | undefined }) {
  if (!status) return null;
  const [label, tone] = STATUS_LABEL[status];
  return <Badge tone={tone}>{label}</Badge>;
}

function pageImage(steps: Step[], doc: string, page: number): string | undefined {
  const reads = steps.filter((s) => s.kind === "read" && s.doc === doc);
  return (reads.find((s) => s.data.page === page) ?? reads[0])?.data.image;
}

function ActionNote({ e }: { e: AuditEntry | undefined }) {
  if (!e) return null;
  const what = e.action === "correct" ? <>corrected to <span className="mono font-medium">{e.value}</span></> : e.action === "reject" ? "rejected" : "accepted";
  return (
    <div className={cx("text-[11px]", e.action === "reject" ? "text-bad" : e.action === "correct" ? "text-info" : "text-ok")}>
      {what} by {e.reviewer}
      {e.reason ? <span className="text-muted"> · {e.reason}</span> : null}
    </div>
  );
}

function FieldRow({
  name,
  value,
  quote,
  ev,
  needs,
  last,
  selected,
  onSelect,
  act,
  closed,
}: {
  name: string;
  value: string | null;
  quote: string | null;
  ev: Evidence | undefined;
  needs: string | undefined;
  last: AuditEntry | undefined;
  selected: boolean;
  onSelect: () => void;
  act: (action: "accept" | "correct" | "reject", extra?: { value?: string; reason?: string }) => Promise<boolean>;
  closed: boolean;
}) {
  const [editing, setEditing] = useState<"correct" | "reject" | null>(null);
  const [text, setText] = useState("");
  const pending = needs && !last;
  const submit = async () => {
    const ok = await act(editing!, editing === "correct" ? { value: text } : { reason: text });
    if (ok) {
      setEditing(null);
      setText("");
    }
  };
  return (
    <tr className={cx("cursor-pointer align-top", selected ? "bg-accent-weak" : "hover:bg-sunk", pending && !selected && "bg-warn-weak/60")} onClick={onSelect}>
      <td className="mono whitespace-nowrap">{name}</td>
      <td className="mono break-all">
        {value ?? <span className="text-faint">null</span>}
        {quote && quote !== value && <div className="text-[11px] text-muted">quote: “{quote}”</div>}
        {ev?.why && <div className="text-[11px] text-warn">{ev.why}</div>}
        <ActionNote e={last} />
      </td>
      <td>
        {ev ? <StatusBadge status={ev.status} /> : needs === "missing" ? <Badge tone="bad">missing</Badge> : <span className="text-faint">–</span>}
        {ev?.basis && (
          <div className="mt-0.5 text-[10.5px] text-faint" title={BASIS_INFO[ev.basis]}>
            {ev.basis}
          </div>
        )}
      </td>
      <td className="whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
        {closed ? null : editing ? (
          <div className="flex flex-col gap-1">
            <input
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder={editing === "correct" ? "value as printed" : "why (optional)"}
              className="mono h-7 w-56 rounded border border-line bg-panel px-2 text-[12px]"
            />
            <div className="flex gap-1">
              <button className="rounded bg-accent px-2 py-0.5 text-[11px] font-semibold text-white dark:text-black" onClick={submit}>
                {editing === "correct" ? "save correction" : "reject value"}
              </button>
              <button className="rounded border border-line px-2 py-0.5 text-[11px]" onClick={() => setEditing(null)}>
                cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex gap-1">
            {value !== null && (
              <button className="rounded border border-line px-1.5 py-0.5 text-[11px] hover:border-ok hover:text-ok" onClick={() => act("accept")} title="I checked it against the document">
                accept
              </button>
            )}
            <button
              className="rounded border border-line px-1.5 py-0.5 text-[11px] hover:border-info hover:text-info"
              onClick={() => {
                setText(value ?? "");
                setEditing("correct");
              }}
            >
              correct
            </button>
            <button className="rounded border border-line px-1.5 py-0.5 text-[11px] hover:border-bad hover:text-bad" onClick={() => setEditing("reject")}>
              reject
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

export function ReviewView({ result, steps }: { result: Result; steps: Step[] }) {
  const runId = result.run_id;
  const [state, setState] = useState<ReviewState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [signErr, setSignErr] = useState<string | null>(null);
  const [reviewer, setReviewerState] = useState(() => lsGet(LS_REVIEWER) ?? "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [verify, setVerify] = useState<string | null>(null);
  const firstPending = (s: ReviewState | null) => s?.pending[0];
  const [sel, setSel] = useState<string | null>(null);
  const setReviewer = (v: string) => {
    setReviewerState(v);
    lsSet(LS_REVIEWER, v);
  };

  useEffect(() => {
    api.review(runId).then(
      (s) => {
        setState(s);
        setSel((cur) => cur ?? firstPending(s) ?? null);
      },
      (e: Error) => setErr(e.message),
    );
  }, [runId]);

  const call = async (fn: () => Promise<ReviewState>): Promise<boolean> => {
    setBusy(true);
    setErr(null);
    try {
      setState(await fn());
      return true;
    } catch (e) {
      setErr((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const act = (doc: string, field: string) => (action: string, extra: { value?: string; reason?: string } = {}) =>
    call(() => api.reviewField(runId, { reviewer, doc, field, action, ...extra }));
  const decide = async (decision: string) => {
    setBusy(true);
    setSignErr(null);
    try {
      setState(await api.reviewDecision(runId, { reviewer, decision, note: note || undefined }));
      setNote("");
    } catch (e) {
      setSignErr((e as Error).message); // shown by the buttons, where the reviewer is looking
    } finally {
      setBusy(false);
    }
  };

  if (!state) return err ? <ErrorBox>{err}</ErrorBox> : <Spinner />;
  const closed = ["approved", "rejected", "info_requested"].includes(state.status);
  const [selDoc, selField] = (sel ?? "").split(".") as [DocType, string];
  const selEv = sel ? result.evidence?.[selDoc]?.[selField] : undefined;
  const img = selDoc ? pageImage(steps, selDoc, selEv?.page ?? 1) : undefined;

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-[16px] font-semibold">Review</h2>
        <DecisionBadge decision={result.decision} />
        <ReviewBadge status={state.status} />
        {state.approved_by.length > 0 && <span className="text-[12px] text-muted">approved by {state.approved_by.join(", ")}</span>}
        <label className="ml-auto flex items-center gap-1.5 text-[12px] text-muted">
          reviewer
          <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="your name" className="h-7 w-44 rounded border border-line bg-panel px-2 text-[12px]" />
        </label>
      </header>
      <div className="rounded border-l-2 border-accent bg-accent-weak px-3 py-2 text-[12px]">
        The pipeline only prepares the file. A person decides: every value the system could not verify must be accepted or corrected by eye, a file
        with flags needs a note, and approval takes two different reviewers. Every action is appended to a hash-chained audit log.
        {state.pending.length > 0 && !closed && (
          <div className="mt-1 font-medium text-warn">
            {state.pending.length} value{state.pending.length > 1 ? "s" : ""} to check by eye: {state.pending.join(", ")}
          </div>
        )}
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}

      <div className="grid gap-3 @4xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="flex flex-col gap-3">
          {img ? (
            <Figure
              src={img}
              caption={sel ? `${DOC_LABEL[selDoc]} · ${selField}${selEv?.bbox ? "" : " · no box: the quote was not found on the page"}` : undefined}
              overlay={
                selEv?.bbox ? (
                  <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
                    <rect
                      x={selEv.bbox[0] - 0.004}
                      y={selEv.bbox[1] - 0.004}
                      width={selEv.bbox[2] - selEv.bbox[0] + 0.008}
                      height={selEv.bbox[3] - selEv.bbox[1] + 0.008}
                      fill={STATUS_COLOR[selEv.status]}
                      fillOpacity={0.18}
                      stroke={STATUS_COLOR[selEv.status]}
                      strokeWidth={2.5}
                      vectorEffect="non-scaling-stroke"
                    />
                  </svg>
                ) : undefined
              }
            />
          ) : (
            <div className="rounded border border-dashed border-line p-6 text-center text-[12px] text-faint">Pick a field to see where it is on the page.</div>
          )}
          <Section title="Why the file is in this queue" pad={false}>
            <div className="p-2">
              <FlagList flags={result.flags} />
            </div>
          </Section>
        </div>

        <div className="flex flex-col gap-3">
          {DOCS.map((doc) => {
            const values = result.fields[doc];
            if (!values) return null;
            return (
              <Section key={doc} title={DOC_LABEL[doc]} pad={false}>
                <table className="dt text-[12px]">
                  <tbody>
                    {Object.entries(values).map(([name, fv]) => {
                      const key = `${doc}.${name}`;
                      return (
                        <FieldRow
                          key={key}
                          name={name}
                          value={fv.value}
                          quote={fv.quote}
                          ev={result.evidence?.[doc]?.[name]}
                          needs={state.needs_eyes[key]}
                          last={state.fields[key]}
                          selected={sel === key}
                          onSelect={() => setSel(key)}
                          act={act(doc, name)}
                          closed={closed || busy}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </Section>
            );
          })}

          {!closed && (
            <Section title="Sign-off">
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={result.flags.length ? "Note (required here: why the flags do not stand in the way, or why you reject)" : "Note (required to reject or ask for information)"}
                className="h-16 w-full rounded border border-line bg-panel p-2 text-[12px]"
              />
              {signErr && <ErrorBox>{signErr}</ErrorBox>}
              <div className="mt-2 flex flex-wrap gap-2">
                <button disabled={busy} onClick={() => decide("approve")} className="h-8 rounded-md bg-ok px-3 text-[12px] font-semibold text-white disabled:opacity-50 dark:text-black">
                  {state.approved_by.length ? "Approve (second reviewer)" : "Approve"}
                </button>
                <button disabled={busy} onClick={() => decide("request_info")} className="h-8 rounded-md border border-line px-3 text-[12px] hover:bg-sunk disabled:opacity-50">
                  Ask the client for more
                </button>
                <button disabled={busy} onClick={() => decide("reject")} className="h-8 rounded-md border border-bad px-3 text-[12px] text-bad hover:bg-bad-weak disabled:opacity-50">
                  Reject
                </button>
              </div>
            </Section>
          )}

          <Section
            title={`Audit trail (${state.entries.length})`}
            pad={false}
            right={
              <button
                className="rounded border border-line px-2 py-0.5 text-[11px] hover:bg-sunk"
                onClick={() =>
                  api.verifyAudit().then(
                    (v) => setVerify(v.ok ? `chain intact: ${v.entries} entries` : `chain broken at entry ${v.broken_at}`),
                    (e: Error) => setVerify(e.message),
                  )
                }
              >
                verify chain
              </button>
            }
          >
            {verify && <div className={cx("px-3 py-1.5 text-[12px]", verify.startsWith("chain intact") ? "text-ok" : "text-bad")}>{verify}</div>}
            {state.entries.length === 0 ? (
              <div className="px-3 py-2 text-[12px] text-faint">Nothing yet.</div>
            ) : (
              <table className="dt text-[11.5px]">
                <tbody>
                  {state.entries.map((e) => (
                    <tr key={e.seq}>
                      <td className="mono text-faint">#{e.seq}</td>
                      <td className="mono whitespace-nowrap text-muted">{e.at.replace("T", " ").replace("+00:00", "Z")}</td>
                      <td>{e.reviewer}</td>
                      <td className="mono">
                        {e.kind === "field" ? `${e.action} ${e.doc}.${e.field}${e.action === "correct" ? ` → ${e.value}` : ""}` : e.decision}
                        {(e.note || e.reason) && <div className="font-sans text-muted">{e.note || e.reason}</div>}
                      </td>
                      <td className="mono text-faint" title={`hash ${e.hash}\nprev ${e.prev}`}>
                        {e.hash.slice(0, 8)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
