import type { ReactNode } from "react";
import { Figure } from "../Figure";
import { DOC_LABEL, bytes, cx, ms, num, prettyJSON } from "../lib";
import type { Result, RunRequest, Step } from "../types";
import { Badge, Collapsible, ErrorBox, JsonBox, KV, Pre, Section, Spinner } from "../ui";
import { ChecksList, CorroborateView, CrossModelView, MrzReconcileView, RouteView, ValidateView } from "./ChecksView";
import { GroundView } from "./GroundView";
import { ReadView } from "./ReadView";

export const KIND_ICON: Record<string, string> = {
  load: "⇩",
  preprocess: "◩",
  read: "▤",
  prompt: "✎",
  llm: "◆",
  normalise: "⇄",
  extract: "⌕",
  mrz: "≡",
  ground: "⌖",
  cross_model: "⇆",
  validate: "✓",
  corroborate: "⛓",
  signature: "✍",
  route: "➜",
};

export interface StepCtx {
  steps: Step[];
  result?: Result;
  request?: RunRequest;
}

function LoadView({ step, ctx }: { step: Step; ctx: StepCtx }) {
  const d = step.data;
  const req = ctx.request ?? ctx.result?.request;
  const fileUrl = req && req.tier !== "upload" ? `/files/${req.tier}/${req.case}/${d.file}` : undefined;
  const willUseLayer = d.reader_mode === "text" || (d.reader_mode === "auto" && d.has_text_layer);
  return (
    <div className="grid gap-3 @3xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-2">
        {(d.images ?? []).map((src: string, i: number) => (
          <Figure key={src} src={src} caption={`page ${i + 1}: original render (PDF at 200 dpi, or the photo as is)`} />
        ))}
      </div>
      <div className="flex flex-col gap-3">
        <Section title="File" pad={false}>
          <KV
            rows={[
              ["file", fileUrl ? <a className="text-accent hover:underline" href={fileUrl} target="_blank">{d.file} ↗</a> : d.file],
              ["size", `${bytes(d.bytes)} (${num(d.bytes)} B)`],
              ["sha256", <span className="text-[11px]">{d.sha256}</span>],
              ["kind", d.kind],
              ["pages", d.pages],
              ["text-layer words / page", JSON.stringify(d.text_layer_words)],
              ["has text layer", String(d.has_text_layer)],
              ["reader mode", d.reader_mode],
            ]}
          />
        </Section>
        <div className="rounded border-l-2 border-accent bg-accent-weak px-3 py-2 text-[12px]">
          {willUseLayer ? (
            <>
              Reader <b>{d.reader_mode}</b> + a text layer with more than 3 words: the next step reads the PDF's embedded text directly. No pre-processing, no OCR.
            </>
          ) : (
            <>
              Reader <b>{d.reader_mode}</b>
              {d.has_text_layer ? " forces OCR" : " and no usable text layer (a scan or a photo)"}: the page goes through pre-processing and Tesseract.
            </>
          )}
          <div className="mt-1 text-muted">The sha256 is the audit trail: it proves which exact bytes were read.</div>
        </div>
      </div>
    </div>
  );
}

function PreprocessView({ step }: { step: Step }) {
  const d = step.data;
  const f = d.flatten ?? {};
  const [w, h] = f.size_before ?? [1, 1];
  const poly = f.applied && f.corners ? (
    <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <polygon
        points={(f.corners as number[][]).map((p) => p.join(",")).join(" ")}
        fill="var(--accent)"
        fillOpacity={0.05}
        stroke="var(--accent)"
        strokeWidth={2.5}
        vectorEffect="non-scaling-stroke"
      />
      {(f.corners as number[][]).map((p, i) => (
        <g key={i}>
          <circle cx={p[0]} cy={p[1]} r={Math.max(w, h) / 120} fill="var(--accent)" />
        </g>
      ))}
    </svg>
  ) : undefined;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2">
        <Figure src={d.before} overlay={poly} caption={<><b>1 · Original.</b> {f.applied ? "Detected page outline in teal (TL, TR, BR, BL)." : "No outline drawn: flattening not applied."}</>} />
        <Figure src={d.flattened} caption={<><b>2 · Flattened.</b> {f.applied ? "Perspective warped to a rectangle." : "Identical to the original."}</>} />
        <Figure src={d.ocr_input} caption={<><b>3 · What Tesseract sees.</b> Greyscale, background light divided out.</>} />
      </div>
      <Section title="flatten_document()" pad={false}>
        <KV
          rows={[
            ["applied", <Badge tone={f.applied ? "ok" : "neutral"}>{String(f.applied)}</Badge>],
            ...(f.reason ? [["reason", f.reason] as [ReactNode, ReactNode]] : []),
            ...(f.corners
              ? [
                  ["corners (px, TL TR BR BL)", (f.corners as number[][]).map((p) => `(${p.map((v) => Math.round(v)).join(", ")})`).join("  ")] as [ReactNode, ReactNode],
                  ["page fraction", `${f.page_fraction} of the image area is page`] as [ReactNode, ReactNode],
                  ["size before → after", `${f.size_before?.join("×")} → ${f.size_after?.join("×")}`] as [ReactNode, ReactNode],
                ]
              : []),
            ["page", d.page],
          ]}
        />
      </Section>
    </div>
  );
}

function PromptView({ step }: { step: Step }) {
  const d = step.data;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        <Badge tone="accent">provider: {d.provider}</Badge>
        <Badge mono>model: {d.model}</Badge>
        <Badge>input mode: {d.input_mode}</Badge>
        <Badge mono>{d.endpoint}</Badge>
        <Badge mono tone="info">prompt v{d.prompt_version}</Badge>
        <Badge>{(d.images ?? []).length} image(s)</Badge>
      </div>
      <Section title="System prompt" pad={false}>
        <Pre className="rounded-none border-0" maxH={320}>
          {d.system}
        </Pre>
      </Section>
      <Section title="User prompt" pad={false}>
        <Pre className="rounded-none border-0" maxH={420}>
          {d.user}
        </Pre>
      </Section>
      {(d.images ?? []).length > 0 && (
        <Section title="Images sent to the model">
          <div className="grid grid-cols-2 gap-2 @3xl:grid-cols-3">
            {(d.images as string[]).map((src) => (
              <Figure key={src} src={src} caption={src.split("/").pop()} />
            ))}
          </div>
        </Section>
      )}
      <Collapsible title="JSON schema (structured output)" defaultOpen={false}>
        <JsonBox value={d.schema} open={2} maxH={480} />
      </Collapsible>
      <Collapsible title="Exact HTTP request body" defaultOpen={false}>
        <JsonBox value={d.request_body} open={4} maxH={560} />
      </Collapsible>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-panel px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-faint">{label}</div>
      <div className="mono text-[16px] font-medium tabular">{value}</div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function LlmView({ step, ctx }: { step: Step; ctx: StepCtx }) {
  const d = step.data;
  const prompt = [...ctx.steps].reverse().find((s) => s.kind === "prompt" && s.doc === step.doc && s.id < step.id);
  const provider = prompt?.data.provider ?? (ctx.request?.extractor ?? "").split(":")[0];
  const local = provider === "ollama";
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {d.cached ? <Badge tone="info">served from disk cache, original latency shown</Badge> : <Badge tone="accent">live HTTP call</Badge>}
        {prompt && <Badge mono>{prompt.data.model}</Badge>}
      </div>
      {d.parse_error && <ErrorBox>parse_error: {d.parse_error}</ErrorBox>}
      <div className="grid grid-cols-2 gap-2 @2xl:grid-cols-5">
        <Stat label="input tokens" value={num(d.input_tokens)} />
        <Stat label="output tokens" value={num(d.output_tokens)} sub="incl. reasoning" />
        <Stat label="reasoning tokens" value={num(d.reasoning_tokens)} sub="hidden thinking" />
        <Stat label="latency" value={d.seconds != null ? `${d.seconds} s` : "–"} />
        <Stat label="cost" value={local ? "free (local)" : d.cost_usd != null ? `$${Number(d.cost_usd).toFixed(5)}` : "–"} />
      </div>
      <Section title="Raw response (pretty-printed)" pad={false}>
        <Pre className="rounded-none border-0" maxH={560}>
          {prettyJSON(d.raw_response)}
        </Pre>
      </Section>
    </div>
  );
}

function NormaliseView({ step }: { step: Step }) {
  const d = step.data;
  const changes: Record<string, [unknown, unknown]> = d.changes ?? {};
  const fields: Record<string, { value: string | null; quote: string | null; page: number | null }> = d.fields ?? {};
  const inj = d.embedded_instructions;
  return (
    <div className="flex flex-col gap-3">
      <div className="text-[12px] text-muted">
        {Object.keys(changes).length} of {Object.keys(fields).length} values changed by normalisation.
      </div>
      <div className="overflow-x-auto rounded-md border border-line bg-panel">
        <table className="dt text-[12px]">
          <thead>
            <tr>
              <th>field</th>
              <th>value before</th>
              <th>after</th>
              <th>quote</th>
              <th>page</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(fields).map(([f, v]) => {
              const ch = changes[f];
              return (
                <tr key={f} className={cx(ch && "bg-warn-weak/60")}>
                  <td className="mono whitespace-nowrap">{f}</td>
                  <td className={cx("mono break-all", ch ? "text-bad line-through decoration-1" : "text-muted")}>{ch ? String(ch[0] ?? "null") : v.value ?? <span className="text-faint">null</span>}</td>
                  <td className={cx("mono break-all", ch && "font-semibold text-ok")}>{ch ? String(ch[1] ?? "null") : <span className="text-faint">unchanged</span>}</td>
                  <td className="mono break-all text-muted">{v.quote ?? <span className="text-faint">null</span>}</td>
                  <td className="mono">{v.page ?? "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {inj !== undefined && (
        <Section title="embedded_instructions (model's prompt-injection report)">
          {inj?.value ? (
            <div className="flex flex-col gap-1">
              <ErrorBox>{inj.value}</ErrorBox>
              <div className="text-[11px] text-muted">
                quote: <span className="mono">{inj.quote}</span> · page {inj.page ?? "–"}
              </div>
            </div>
          ) : (
            <div className="text-[12px] text-muted">The model reported no text addressed to an AI system (value = null).</div>
          )}
        </Section>
      )}
    </div>
  );
}

function ExtractView({ step }: { step: Step }) {
  const pats: Record<string, { pattern: string; match: string | string[] | null }> = step.data.patterns ?? {};
  return (
    <div className="flex flex-col gap-2">
      <div className="text-[12px] text-muted">The baseline: one hand-written regex per field, run over the OCR text. No model. Brittle to layout, language and OCR noise.</div>
      <div className="overflow-x-auto rounded-md border border-line bg-panel">
        <table className="dt text-[12px]">
          <thead>
            <tr>
              <th>field</th>
              <th>regex</th>
              <th>match</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(pats).map(([f, p]) => {
              const hit = p.match !== null && p.match !== undefined;
              return (
                <tr key={f}>
                  <td className="mono whitespace-nowrap">{f}</td>
                  <td className="mono break-all text-[11px] text-muted">{p.pattern}</td>
                  <td className={cx("mono break-all", hit ? "text-ok" : "text-faint")}>
                    {Array.isArray(p.match) ? p.match.map((m, i) => <div key={i}>{m}</div>) : hit ? p.match : "no match"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SignatureView({ step, ctx }: { step: Step; ctx: StepCtx }) {
  const check = step.data.check;
  const band = check?.inputs ?? {};
  const read = ctx.steps.find((s) => s.kind === "read" && s.doc === step.doc && s.data.page === (band.page ?? 1));
  const box = band.bbox as [number, number, number, number] | undefined;
  return (
    <div className="grid gap-3 @3xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <Figure
        src={read?.data.image}
        caption="The band above the signature label, where the ink is measured (printed lines removed first)."
        overlay={
          box ? (
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
              <rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} fill="var(--accent)" fillOpacity={0.12} stroke="var(--accent)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
            </svg>
          ) : undefined
        }
      />
      <div className="flex flex-col gap-3">
        {check && <ChecksList checks={[check]} />}
        <div className="text-[12px] text-muted">
          A pixel test, not a model's opinion: is anything written where the signature goes? It cannot tell whose signature it is. Under CDB 20
          art. 63(b) an incomplete Form A is a minor breach only if it is signed, so this is the Form A field that matters most.
        </div>
      </div>
    </div>
  );
}

function Body({ step, ctx }: { step: Step; ctx: StepCtx }) {
  switch (step.kind) {
    case "load":
      return <LoadView step={step} ctx={ctx} />;
    case "preprocess":
      return <PreprocessView step={step} />;
    case "read":
      return <ReadView step={step} />;
    case "prompt":
      return <PromptView step={step} />;
    case "llm":
      return <LlmView step={step} ctx={ctx} />;
    case "normalise":
      return <NormaliseView step={step} />;
    case "extract":
      return <ExtractView step={step} />;
    case "mrz":
      return <MrzReconcileView step={step} />;
    case "ground":
      return <GroundView step={step} steps={ctx.steps} result={ctx.result} />;
    case "cross_model":
      return <CrossModelView step={step} />;
    case "validate":
      return <ValidateView step={step} />;
    case "corroborate":
      return <CorroborateView step={step} />;
    case "route":
      return <RouteView step={step} />;
    case "signature":
      return <SignatureView step={step} ctx={ctx} />;
    default:
      return Array.isArray(step.data.checks) ? <ChecksList checks={step.data.checks} /> : <JsonBox value={step.data} />;
  }
}

export function StepDetail({ step, ctx, secondModel }: { step: Step; ctx: StepCtx; secondModel?: boolean }) {
  const running = step.ms === null;
  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[18px] text-accent">{KIND_ICON[step.kind] ?? "•"}</span>
          <h2 className="text-[16px] font-semibold">{step.title}</h2>
          <Badge mono>{step.kind}</Badge>
          {step.doc && <Badge>{DOC_LABEL[step.doc]}</Badge>}
          {secondModel && <Badge tone="info">second model</Badge>}
          <span className="mono ml-auto text-[12px] text-muted">
            step #{step.id} · {running ? "running" : ms(step.ms)}
          </span>
          {step.status === "error" ? <Badge tone="bad">error</Badge> : running ? <Spinner /> : <Badge tone="ok">ok</Badge>}
        </div>
        {step.explain && <p className="max-w-[90ch] text-[12.5px] text-muted">{step.explain}</p>}
      </header>
      {step.data.error && <ErrorBox>{step.data.error}</ErrorBox>}
      {running ? (
        <div className="flex items-center gap-2 rounded-md border border-dashed border-line p-6 text-muted">
          <Spinner /> This step is running. Its inputs and outputs appear when it finishes.
        </div>
      ) : (
        <Body step={step} ctx={ctx} />
      )}
      {!running && (
        <Collapsible title="Raw step JSON">
          <JsonBox value={step} open={1} maxH={520} />
        </Collapsible>
      )}
    </div>
  );
}
