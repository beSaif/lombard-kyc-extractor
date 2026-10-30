import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, lsGet, lsSet, useFetch } from "../api";
import { DOCS, DOC_LABEL, cx } from "../lib";
import { href, navigate, type Route } from "../router";
import type { DocType, Issue, IssueRegion, Result, RunIssues, RunState, Step } from "../types";
import { Badge, ErrorBox, Section, Spinner, StatusBadge } from "../ui";
import { ExtractorSelect, LS_EXTRACTOR } from "./Pipeline";

// The client's side of the pipeline: hand in the documents, wait, and see what a reviewer will be asked to
// look at, each reason cropped from the page it is on. Everything here is a view of a normal upload run.

const DOC_HINT: Record<DocType, string> = {
  passport: "The data page, with the two lines of <<< at the bottom",
  form_a: "Signed, with the beneficial owner's details",
  proof_of_address: "A utility bill or bank statement from the last 90 days",
};

type Box = [number, number, number, number];

const sevColor = (severity: string) => (severity === "high" ? "var(--bad)" : "var(--warn)");

// ---------------------------------------------------------------- upload

function DropZone({ doc, file, onFile }: { doc: DocType; file: File | undefined; onFile: (f: File | undefined) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={cx(
        "flex min-h-[150px] cursor-pointer flex-col justify-between gap-2 rounded-md border-2 border-dashed p-3 transition-colors",
        over ? "border-accent bg-accent-weak" : file ? "border-ok/50 bg-ok-weak/40" : "border-line-strong bg-panel hover:border-accent",
      )}
    >
      <div>
        <div className="font-semibold">{DOC_LABEL[doc]}</div>
        <div className="text-[12px] text-muted">{DOC_HINT[doc]}</div>
      </div>
      {file ? (
        <div className="flex items-center gap-2 text-[12px]">
          <span className="text-ok">✓</span>
          <span className="mono min-w-0 flex-1 truncate">{file.name}</span>
          <button
            className="rounded border border-line px-1.5 text-[11px] text-muted hover:text-bad"
            onClick={(e) => {
              e.stopPropagation();
              onFile(undefined);
              if (input.current) input.current.value = "";
            }}
          >
            remove
          </button>
        </div>
      ) : (
        <div className="text-[12px] text-faint">Drop a PDF, JPEG or PNG here, or click to choose</div>
      )}
      <input ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
    </div>
  );
}

function UploadForm() {
  const [files, setFiles] = useState<Partial<Record<DocType, File>>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const extractors = useFetch("extractors", api.extractors);
  const localDefault = extractors.data?.find((e) => e.provider === "ollama" && e.mode === "both")?.spec ?? "rules";
  const [chosen, setChosen] = useState<string | null>(null);
  const extractor = chosen ?? lsGet(LS_EXTRACTOR) ?? localDefault;
  const ex = extractors.data?.find((e) => e.spec === extractor);
  const missing = DOCS.filter((d) => !files[d]);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const up = await api.upload(files as Record<string, File>);
      const { run_id } = await api.startRun({ tier: "upload", case: up.case, extractor, reader: "auto" });
      navigate("submit", { run: run_id });
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-6">
      <div>
        <h1 className="text-[20px] font-semibold">Open an account: hand in your documents</h1>
        <p className="mt-1 text-[13px] text-muted">
          Upload the three documents below. They are read, checked against each other, and either prepared for a quick sign-off or sent to a
          reviewer with the exact places on the page that need a second look.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {DOCS.map((d) => (
          <DropZone
            key={d}
            doc={d}
            file={files[d]}
            onFile={(f) =>
              setFiles((cur) => {
                const next = { ...cur };
                if (f) next[d] = f;
                else delete next[d];
                return next;
              })
            }
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-panel px-3 py-2.5">
        <label className="flex items-center gap-1.5 text-[12px] text-muted">
          read with
          {extractors.data && (
            <ExtractorSelect
              value={extractor}
              extractors={extractors.data}
              onChange={(v) => {
                lsSet(LS_EXTRACTOR, v);
                setChosen(v);
              }}
            />
          )}
        </label>
        <span className={cx("text-[12px]", ex && !ex.local ? "text-warn" : "text-muted")}>
          {ex ? (ex.local ? "Stays on this machine." : `The page images are sent to ${ex.provider}.`) : ""}
        </span>
        <button
          disabled={busy || missing.length === DOCS.length}
          onClick={submit}
          className="ml-auto h-9 rounded-md bg-accent px-5 font-semibold text-white hover:opacity-90 disabled:opacity-50 dark:text-black"
        >
          {busy ? "Sending…" : "Submit documents"}
        </button>
      </div>
      {missing.length > 0 && missing.length < DOCS.length && (
        <div className="text-[12px] text-warn">
          No {missing.map((d) => DOC_LABEL[d].toLowerCase()).join(" or ")} yet: you can still submit, but the file will go to manual review as
          incomplete.
        </div>
      )}
      {err && <ErrorBox>{err}</ErrorBox>}
    </div>
  );
}

// ---------------------------------------------------------------- progress

function stages(steps: Step[], docs: DocType[]): { label: string; state: "done" | "active" | "todo" }[] {
  const has = (pred: (s: Step) => boolean) => steps.some(pred);
  const out: { label: string; state: "done" | "active" | "todo" }[] = docs.map((d) => ({
    label: `Reading your ${DOC_LABEL[d].toLowerCase()}`,
    state: has((s) => s.doc === d && s.kind === "ground" && s.ms !== null) ? "done" : has((s) => s.doc === d) ? "active" : "todo",
  }));
  out.push({
    label: "Checking the documents against each other",
    state: has((s) => s.kind === "corroborate" && s.ms !== null) ? "done" : has((s) => s.kind === "validate") ? "active" : "todo",
  });
  out.push({ label: "Deciding who signs off", state: has((s) => s.kind === "route" && s.ms !== null) ? "done" : "todo" });
  // Whatever runs first and is not done yet is the one in progress.
  const first = out.findIndex((s) => s.state !== "done");
  if (first >= 0 && out.slice(first).every((s) => s.state === "todo")) out[first].state = "active";
  return out;
}

function Progress({ run }: { run: RunState }) {
  const steps = run.steps ?? [];
  const req = run.request;
  const handedIn = useFetch(req ? `case:${req.tier}:${req.case}` : null, () => api.caseDetail(req!.tier, req!.case));
  const docs = handedIn.data ? DOCS.filter((d) => handedIn.data!.files.some((f) => f.startsWith(`${d}.`))) : DOCS;
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-10">
      <h1 className="text-[20px] font-semibold">Checking your documents…</h1>
      <ol className="flex flex-col gap-2 rounded-md border border-line bg-panel p-4">
        {stages(steps, docs).map((s, i) => (
          <li key={i} className={cx("flex items-center gap-2.5", s.state === "todo" && "text-faint")}>
            {s.state === "done" ? <span className="w-3 text-ok">✓</span> : s.state === "active" ? <Spinner /> : <span className="w-3">·</span>}
            {s.label}
          </li>
        ))}
      </ol>
      <div className="text-[12px] text-faint">{run.elapsed ? `${run.elapsed.toFixed(0)} s` : ""} · this takes longer with a local model</div>
    </div>
  );
}

// ---------------------------------------------------------------- crops and the document viewer

/** The part of a page around a box, with the box drawn on it. Click to open the whole document. */
function Crop({ src, bbox, color, dashed, onClick }: { src: string; bbox: Box; color: string; dashed: boolean; onClick: () => void }) {
  const [size, setSize] = useState<[number, number] | null>(null);
  const [x0, y0, x1, y1] = bbox;
  const ratio = size ? size[0] / size[1] : 0.7;
  // Some context around the box, and never a crop narrower than about 2.4:1 (a line, not a column).
  const px = Math.max(0.05, (x1 - x0) * 0.2);
  const py = Math.max(0.025, (y1 - y0) * 1.2);
  let [cx0, cy0, cx1, cy1] = [x0 - px, y0 - py, x1 + px, y1 + py];
  const minW = Math.min(1, (2.4 * (cy1 - cy0)) / ratio);
  if (cx1 - cx0 < minW) {
    const grow = (minW - (cx1 - cx0)) / 2;
    [cx0, cx1] = [cx0 - grow, cx1 + grow];
  }
  if (cx0 < 0) [cx0, cx1] = [0, Math.min(1, cx1 - cx0)];
  if (cx1 > 1) [cx0, cx1] = [Math.max(0, cx0 - (cx1 - 1)), 1];
  [cy0, cy1] = [Math.max(0, cy0), Math.min(1, cy1)];
  const cw = cx1 - cx0;
  const ch = cy1 - cy0;
  const aspect = (cw * ratio) / ch;
  const pctX = (v: number) => `${((v - cx0) / cw) * 100}%`;
  const pctY = (v: number) => `${((v - cy0) / ch) * 100}%`;
  return (
    <button
      onClick={onClick}
      title="Open the whole document"
      className="group relative block w-full overflow-hidden rounded border border-line bg-sunk"
      style={{ aspectRatio: aspect, maxWidth: `${170 * aspect}px` }}
    >
      <img
        src={src}
        alt=""
        draggable={false}
        onLoad={(e) => setSize([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight])}
        className={cx("absolute max-w-none select-none", !size && "opacity-0")}
        style={{ width: `${100 / cw}%`, height: `${100 / ch}%`, left: `${(-cx0 / cw) * 100}%`, top: `${(-cy0 / ch) * 100}%` }}
      />
      <span
        className="absolute rounded-[2px]"
        style={{
          left: pctX(x0 - 0.004),
          top: pctY(y0 - 0.004),
          width: `${((x1 - x0 + 0.008) / cw) * 100}%`,
          height: `${((y1 - y0 + 0.008) / ch) * 100}%`,
          border: `2px ${dashed ? "dashed" : "solid"} ${color}`,
          background: `color-mix(in srgb, ${color} 14%, transparent)`,
        }}
      />
      <span className="absolute right-1.5 bottom-1.5 rounded border border-line bg-panel/90 px-1.5 py-0.5 text-[11px] text-muted opacity-0 shadow-sm group-hover:opacity-100">
        ⤢ whole document
      </span>
    </button>
  );
}

export interface Focus {
  doc: DocType;
  page: number;
  key?: string; // `${issue id}:${region index}`, or `field:${doc}.${name}`
}

interface Mark {
  key: string;
  doc: DocType;
  page: number;
  bbox: Box;
  color: string;
  dashed: boolean;
  label: string;
  issue: boolean; // false: just where a value was read
}

function MarkList({ title, marks, active, multiPage, go, empty }: { title: string; marks: Mark[]; active?: string; multiPage: boolean; go: (m: Mark) => void; empty?: string }) {
  if (!marks.length && !empty) return null;
  return (
    <div className="mb-4">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">{title}</div>
      {!marks.length && <div className="text-[12px] text-faint">{empty}</div>}
      <ul className="flex flex-col gap-1">
        {marks.map((m) => (
          <li key={m.key}>
            <button
              onClick={() => go(m)}
              className={cx("w-full rounded border px-2 py-1 text-left text-[12px]", m.key === active ? "border-accent bg-accent-weak" : "border-line hover:bg-sunk")}
            >
              <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: m.color }} />
              {m.label}
              {multiPage && <span className="text-faint"> · p{m.page}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DocViewer({ pages, marks, focus, onClose }: { pages: RunIssues["pages"]; marks: Mark[]; focus: Focus; onClose: () => void }) {
  const [doc, setDoc] = useState<DocType>(focus.doc);
  const [page, setPage] = useState(focus.page);
  const [active, setActive] = useState(focus.key);
  const [zoom, setZoom] = useState(1);
  const focused = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const docPages = pages[doc] ?? [];
  const img = (docPages.find((p) => p.page === page) ?? docPages[0])?.image;
  const here = marks.filter((m) => m.doc === doc && m.page === page);
  const docs = DOCS.filter((d) => pages[d]?.length);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)));
      if (e.key === "-") setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [onClose]);
  useEffect(() => {
    if (loaded) focused.current?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
  }, [loaded, active, zoom]);

  const go = (m: Mark) => {
    if (m.doc !== doc || m.page !== page) setLoaded(false);
    setDoc(m.doc);
    setPage(m.page);
    setActive(m.key);
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex flex-col bg-black/70" onClick={onClose}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-panel px-4 py-2 text-[12px]" onClick={(e) => e.stopPropagation()}>
        <div className="inline-flex rounded-md border border-line bg-sunk p-0.5">
          {docs.map((d) => (
            <button
              key={d}
              onClick={() => {
                setDoc(d);
                setPage(pages[d]![0].page);
                setLoaded(false);
              }}
              className={cx("rounded px-2.5 py-1", d === doc ? "bg-panel font-medium shadow-sm" : "text-muted hover:text-fg")}
            >
              {DOC_LABEL[d]}
              {marks.some((m) => m.doc === d) && <span className="ml-1 text-bad">●</span>}
            </button>
          ))}
        </div>
        {docPages.length > 1 &&
          docPages.map((p) => (
            <button
              key={p.page}
              onClick={() => {
                setPage(p.page);
                setLoaded(false);
              }}
              className={cx("rounded border px-2 py-0.5", p.page === page ? "border-accent text-fg" : "border-line text-muted")}
            >
              page {p.page}
            </button>
          ))}
        <span className="text-muted">Zoom</span>
        <input type="range" min={0.5} max={4} step={0.25} value={zoom} onChange={(e) => setZoom(+e.target.value)} className="w-40 accent-[var(--accent)]" />
        <span className="mono w-10 tabular">{Math.round(zoom * 100)}%</span>
        <span className="ml-auto text-faint">+/- to zoom, Esc to close</span>
        <button className="rounded border border-line px-2 py-0.5 hover:bg-sunk" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="flex min-h-0 flex-1" onClick={(e) => e.stopPropagation()}>
        <div className="min-w-0 flex-1 overflow-auto p-6">
          {img ? (
            <div className="relative mx-auto bg-panel" style={{ width: `${zoom * 100}%`, maxWidth: zoom === 1 ? 1000 : undefined }}>
              <img src={img} alt="" className="block w-full select-none" draggable={false} onLoad={() => setLoaded(true)} />
              {here.map((m) => {
                const on = m.key === active;
                return (
                  <div
                    key={m.key}
                    ref={on ? focused : undefined}
                    onClick={() => setActive(m.key)}
                    title={m.label}
                    className={cx("absolute cursor-pointer rounded-[2px]", on && "z-10")}
                    style={{
                      left: `${(m.bbox[0] - 0.004) * 100}%`,
                      top: `${(m.bbox[1] - 0.004) * 100}%`,
                      width: `${(m.bbox[2] - m.bbox[0] + 0.008) * 100}%`,
                      height: `${(m.bbox[3] - m.bbox[1] + 0.008) * 100}%`,
                      border: `${on ? 3 : m.issue ? 1.5 : 1}px ${m.dashed ? "dashed" : "solid"} ${m.color}`,
                      background: `color-mix(in srgb, ${m.color} ${on ? 20 : m.issue ? 8 : 0}%, transparent)`,
                      opacity: on || m.issue ? 1 : 0.45,
                      boxShadow: on ? `0 0 0 4px color-mix(in srgb, ${m.color} 25%, transparent)` : undefined,
                    }}
                  />
                );
              })}
            </div>
          ) : (
            <div className="mx-auto max-w-md rounded border border-dashed border-line bg-panel p-6 text-center text-faint">No page image for this document.</div>
          )}
        </div>
        <aside className="hidden w-72 shrink-0 overflow-auto border-l border-line bg-panel p-3 md:block">
          <MarkList title="Needs a look" marks={marks.filter((m) => m.doc === doc && m.issue)} active={active} multiPage={docPages.length > 1} go={go} empty="Nothing to check on this document." />
          <MarkList title="Values read" marks={marks.filter((m) => m.doc === doc && !m.issue)} active={active} multiPage={docPages.length > 1} go={go} />
        </aside>
      </div>
    </div>,
    document.body,
  );
}

// ---------------------------------------------------------------- outcome

function pageImage(pages: RunIssues["pages"], doc: DocType, page: number): string | undefined {
  const ps = pages[doc] ?? [];
  return (ps.find((p) => p.page === page) ?? ps[0])?.image;
}

function RegionView({ issue, r, i, pages, open }: { issue: Issue; r: IssueRegion; i: number; pages: RunIssues["pages"]; open: (f: Focus) => void }) {
  const src = pageImage(pages, r.doc, r.page);
  const focus = { doc: r.doc, page: r.page, key: `${issue.id}:${i}` };
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-baseline gap-x-2 text-[12px]">
        <span className="font-medium">{r.label}</span>
        <span className="text-faint">{DOC_LABEL[r.doc]}</span>
        {r.value && <span className="mono min-w-0 break-all">“{r.value}”</span>}
        {r.status && r.status !== "verified" && <StatusBadge status={r.status} />}
      </div>
      {src && r.bbox ? (
        <Crop src={src} bbox={r.bbox} color={sevColor(issue.severity)} dashed={!r.exact} onClick={() => open(focus)} />
      ) : src ? (
        <button onClick={() => open(focus)} className="flex items-center gap-3 rounded border border-dashed border-line p-2 text-left text-[12px] text-muted hover:bg-sunk">
          <img src={src} alt="" className="h-20 rounded border border-line" />
          <span>Not found on the page. Open the document to look for it.</span>
        </button>
      ) : (
        <div className="rounded border border-dashed border-line p-2 text-[12px] text-faint">No page to show: the document was not uploaded.</div>
      )}
      {r.note && <div className="text-[11px] text-muted">{r.note}</div>}
    </div>
  );
}

function IssueCard({ issue, pages, open }: { issue: Issue; pages: RunIssues["pages"]; open: (f: Focus) => void }) {
  return (
    <li className="flex flex-col gap-2.5 rounded-md border border-line bg-panel p-3" style={{ borderLeft: `3px solid ${sevColor(issue.severity)}` }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{issue.title}</span>
        <Badge mono tone={issue.severity === "high" ? "bad" : "warn"}>
          {issue.code}
        </Badge>
      </div>
      <div className="text-[12px] text-muted">{issue.message}</div>
      {issue.missing_doc && <div className="text-[12px]">Upload a {DOC_LABEL[issue.missing_doc].toLowerCase()} to complete the file.</div>}
      {issue.regions.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {issue.regions.map((r, i) => (
            <RegionView key={i} issue={issue} r={r} i={i} pages={pages} open={open} />
          ))}
        </div>
      )}
    </li>
  );
}

function FieldsRead({ result, pages, open }: { result: Result; pages: RunIssues["pages"]; open: (f: Focus) => void }) {
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {DOCS.map((doc) => {
        const values = result.fields[doc];
        return (
          <Section key={doc} title={DOC_LABEL[doc]} pad={false}>
            {!values ? (
              <div className="px-3 py-2 text-[12px] text-faint">not uploaded</div>
            ) : (
              <table className="dt text-[12px]">
                <tbody>
                  {Object.entries(values).map(([name, fv]) => {
                    const ev = result.evidence?.[doc]?.[name];
                    const clickable = !!(ev?.bbox && pages[doc]);
                    return (
                      <tr
                        key={name}
                        className={cx(clickable && "cursor-pointer hover:bg-sunk")}
                        onClick={() => clickable && open({ doc, page: ev!.page ?? 1, key: `field:${doc}.${name}` })}
                      >
                        <td className="text-muted">{name.replace(/_/g, " ")}</td>
                        <td className={cx("mono", name.startsWith("mrz") ? "break-all" : "break-words")}>{fv.value ?? <span className="text-faint">–</span>}</td>
                        <td>{ev && <StatusBadge status={ev.status} />}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Section>
        );
      })}
    </div>
  );
}

function Outcome({ result }: { result: Result }) {
  const issues = useFetch<RunIssues>(`issues:${result.run_id}`, () => api.issues(result.run_id));
  const [focus, setFocus] = useState<Focus | null>(null);
  const marks = useMemo<Mark[]>(() => {
    if (!issues.data) return [];
    const out: Mark[] = [];
    for (const issue of issues.data.issues)
      issue.regions.forEach((r, i) => {
        if (r.bbox)
          out.push({ key: `${issue.id}:${i}`, doc: r.doc, page: r.page, bbox: r.bbox, color: sevColor(issue.severity), dashed: !r.exact, label: `${issue.title}: ${r.label}`, issue: true });
      });
    // Every value read, so a click in "What we read" lands on its box too. Drawn first, under the issues.
    const read: Mark[] = DOCS.flatMap((doc) =>
      Object.entries(result.evidence?.[doc] ?? {})
        .filter(([, ev]) => ev.bbox)
        .map(([name, ev]) => ({ key: `field:${doc}.${name}`, doc, page: ev.page ?? 1, bbox: ev.bbox!, color: "var(--info)", dashed: ev.method === "not_found", label: name.replace(/_/g, " "), issue: false })),
    );
    return [...read, ...out];
  }, [issues.data, result]);

  const quick = result.decision === "pre_filled_review";
  const n = issues.data?.issues.length ?? result.flags.length;
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-6">
      <div className={cx("flex flex-wrap items-center gap-4 rounded-md border p-4", quick ? "border-ok/40 bg-ok-weak" : "border-warn/40 bg-warn-weak")}>
        <span className={cx("text-[28px] leading-none", quick ? "text-ok" : "text-warn")}>{quick ? "✓" : "!"}</span>
        <div className="min-w-0 flex-1">
          <div className="text-[17px] font-semibold">{quick ? "Everything checks out" : `A reviewer needs to look at ${n} thing${n === 1 ? "" : "s"}`}</div>
          <div className="text-[12px] text-muted">
            {quick
              ? "Every value was found on the page and the documents agree. The file goes to the quick queue, pre-filled, for a compliance officer to sign off."
              : "The file goes to manual review. Each reason is shown below with the part of the page it is about; click one to see it on the whole document."}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={href("submit")} className="h-8 rounded-md border border-line bg-panel px-3 text-[12px] leading-8 hover:bg-sunk">
            Submit another file
          </a>
          <a
            href={href("pipeline", { tier: result.request?.tier ?? "upload", case: result.case, extractor: result.extractor, run: result.run_id, step: "review" })}
            className="h-8 rounded-md border border-line bg-panel px-3 text-[12px] leading-8 hover:bg-sunk"
            title="The same run in the reviewer workbench: accept or correct values, sign off"
          >
            Open in the reviewer workbench →
          </a>
        </div>
      </div>

      {issues.error && <ErrorBox>{issues.error}</ErrorBox>}
      {!quick && (issues.data ? (
        <ul className="flex flex-col gap-3">
          {issues.data.issues.map((issue) => (
            <IssueCard key={issue.id} issue={issue} pages={issues.data!.pages} open={setFocus} />
          ))}
        </ul>
      ) : (
        <Spinner />
      ))}

      {issues.data && (
        <>
          <h2 className="mt-2 text-[14px] font-semibold">What we read from your documents</h2>
          <FieldsRead result={result} pages={issues.data.pages} open={setFocus} />
        </>
      )}
      {focus && issues.data && <DocViewer pages={issues.data.pages} marks={marks} focus={focus} onClose={() => setFocus(null)} />}
    </div>
  );
}

// ---------------------------------------------------------------- page

function RunPanel({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const poll = () =>
      api.run(runId).then(
        (r) => {
          if (!alive) return;
          setRun(r);
          if (r.status === "running") timer = window.setTimeout(poll, 700);
        },
        (e: Error) => alive && setErr(e.message),
      );
    poll();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [runId]);
  if (err) return <div className="mx-auto max-w-xl p-6"><ErrorBox>{err}</ErrorBox></div>;
  if (!run) return <div className="p-6"><Spinner /></div>;
  if (run.status === "error")
    return (
      <div className="mx-auto flex max-w-xl flex-col gap-3 px-4 py-10">
        <h1 className="text-[18px] font-semibold">Something went wrong reading the documents</h1>
        <ErrorBox>{run.error}</ErrorBox>
        <a href={href("submit")} className="text-accent">← try again</a>
      </div>
    );
  if (run.status === "running" || !run.result) return <Progress run={run} />;
  return <Outcome result={run.result} />;
}

export function SubmitPage({ route }: { route: Route }) {
  const runId = route.params.run;
  return <div className="min-h-0 flex-1 overflow-auto">{runId ? <RunPanel key={runId} runId={runId} /> : <UploadForm />}</div>;
}
