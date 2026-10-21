import { useState } from "react";
import { api, useFetch } from "../api";
import { CodeBlock } from "../Code";
import { cx } from "../lib";
import { setParams, type Route } from "../router";
import { ErrorBox, Spinner } from "../ui";

const MAP: { label: string; ref: string; note: string }[] = [
  { label: "Load", ref: "kyc_demo.read.load_pages", note: "PDF → images + text layer" },
  { label: "Pre-process", ref: "kyc_demo.read.flatten_document", note: "perspective + light" },
  { label: "OCR", ref: "kyc_demo.read.ocr_page", note: "Tesseract, 2 passes" },
  { label: "Prompt", ref: "kyc_demo.extract.build_user_prompt", note: "fields + doc text" },
  { label: "Model", ref: "kyc_demo.extract.LLMExtractor.call", note: "HTTP, cached" },
  { label: "Normalise", ref: "kyc_demo.extract.postprocess", note: "dates, ISO codes" },
  { label: "Ground", ref: "kyc_demo.ground.locate", note: "quote ↔ OCR words" },
  { label: "Validate", ref: "kyc_demo.validate.check_passport", note: "MRZ, expiry, cross" },
  { label: "Corroborate", ref: "kyc_demo.validate.corroborate", note: "rescue unverified" },
  { label: "Route", ref: "kyc_demo.pipeline.run_case", note: "decision + flags" },
];

export function CodePage({ route }: { route: Route }) {
  const mods = useFetch("modules", api.modules);
  const refName = route.params.ref || null;
  const ref = useFetch(refName ? `code:${refName}` : null, () => api.code(refName!));
  const [q, setQ] = useState("");
  const list = mods.data ?? [];
  const byRef = ref.data && list.find((m) => m.file === ref.data!.file);
  const current = byRef ?? list.find((m) => m.module === route.params.module) ?? list.find((m) => m.module === "kyc_demo.pipeline") ?? list[0];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-line bg-panel px-4 py-2.5">
        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">Pipeline map · click a stage to open its main function</div>
        <div className="flex flex-wrap items-stretch gap-1">
          {MAP.map((m, i) => (
            <div key={m.ref} className="flex items-center gap-1">
              <button
                onClick={() => setParams({ ref: m.ref, module: null }, false)}
                className={cx(
                  "flex flex-col rounded-md border px-2 py-1 text-left",
                  refName === m.ref ? "border-accent bg-accent-weak" : "border-line hover:border-accent",
                )}
                title={m.ref}
              >
                <span className="text-[12px] font-semibold">{m.label}</span>
                <span className="mono text-[10px] text-muted">{m.ref.split(".").slice(2).join(".")}()</span>
                <span className="text-[10px] text-faint">{m.note}</span>
              </button>
              {i < MAP.length - 1 && <span className="text-faint">→</span>}
            </div>
          ))}
        </div>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)]">
        <aside className="min-h-0 overflow-auto border-r border-line bg-panel">
          {mods.loading && !mods.data && (
            <div className="p-3">
              <Spinner />
            </div>
          )}
          {mods.error && <ErrorBox>{mods.error}</ErrorBox>}
          {list.map((m) => (
            <button
              key={m.module}
              onClick={() => setParams({ module: m.module, ref: null }, false)}
              className={cx("block w-full border-b border-line px-3 py-2 text-left hover:bg-sunk", current?.module === m.module && "bg-accent-weak")}
            >
              <div className="flex items-center gap-2">
                <span className="mono text-[12px] font-medium">{m.module.replace("kyc_demo.", "")}</span>
                <span className="mono ml-auto text-[10.5px] text-faint">{m.lines} lines</span>
              </div>
              <div className="line-clamp-2 text-[11.5px] text-muted">{(m.doc ?? "").split("\n")[0]}</div>
            </button>
          ))}
        </aside>
        <main className="flex min-h-0 flex-col gap-2 p-3">
          {current && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="mono text-[13px] font-semibold">{current.file}</span>
                <span className="mono text-[11px] text-faint">{current.lines} lines</span>
                {ref.data && byRef && (
                  <span className="mono rounded bg-warn-weak px-1.5 text-[11px] text-warn">
                    {ref.data.ref.split(".").slice(2).join(".")} · lines {ref.data.start}–{ref.data.end}
                  </span>
                )}
                {ref.error && <span className="text-[11px] text-bad">{ref.error}</span>}
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="filter lines…"
                  className="mono ml-auto h-7 w-64 rounded-md border border-line bg-panel px-2 text-[12px] outline-none focus:border-accent"
                />
              </div>
              {current.doc && <div className="rounded border-l-2 border-accent bg-accent-weak px-3 py-2 text-[12px] whitespace-pre-wrap">{current.doc}</div>}
              <div className="min-h-0 flex-1">
                <CodeBlock
                  source={current.source}
                  start={1}
                  filter={q}
                  highlight={ref.data && byRef ? [ref.data.start, ref.data.end] : null}
                  scrollTo={ref.data && byRef && !q ? ref.data.start : null}
                  maxH="100%"
                />
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
