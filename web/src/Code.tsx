import { Highlight, type PrismTheme } from "prism-react-renderer";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, useFetch } from "./api";
import { cx } from "./lib";
import { ErrorBox, Spinner } from "./ui";

const theme: PrismTheme = {
  plain: { color: "var(--fg)", backgroundColor: "transparent" },
  styles: [
    { types: ["comment", "prolog", "doctype", "cdata"], style: { color: "var(--syn-com)", fontStyle: "italic" } },
    { types: ["keyword", "boolean", "important"], style: { color: "var(--syn-kw)" } },
    { types: ["string", "char", "attr-value", "triple-quoted-string", "string-interpolation"], style: { color: "var(--syn-str)" } },
    { types: ["number", "constant"], style: { color: "var(--syn-num)" } },
    { types: ["function", "class-name"], style: { color: "var(--syn-fn)" } },
    { types: ["builtin", "decorator", "annotation"], style: { color: "var(--syn-builtin)" } },
    { types: ["operator", "punctuation"], style: { color: "var(--syn-op)" } },
  ],
};

/**
 * Highlighted Python with real line numbers.
 * `highlight` marks a line range (absolute numbers); `filter` keeps only lines containing the text.
 */
export function CodeBlock({
  source,
  start = 1,
  highlight,
  filter,
  scrollTo,
  maxH,
  language = "python",
}: {
  source: string;
  start?: number;
  highlight?: [number, number] | null;
  filter?: string;
  scrollTo?: number | null;
  maxH?: number | string;
  language?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const q = (filter || "").toLowerCase();
  useEffect(() => {
    if (!scrollTo || !box.current) return;
    const el = box.current.querySelector<HTMLElement>(`[data-line="${scrollTo}"]`);
    if (el) box.current.scrollTop = el.offsetTop - 40;
  }, [scrollTo, source]);
  return (
    <div ref={box} className="relative overflow-auto rounded border border-line bg-code" style={{ maxHeight: maxH }}>
      <Highlight code={source.replace(/\n$/, "")} language={language} theme={theme}>
        {({ tokens, getLineProps, getTokenProps }) => {
          const rows = tokens.map((line, i) => ({ line, n: start + i }));
          const shown = q ? rows.filter(({ line }) => line.map((t) => t.content).join("").toLowerCase().includes(q)) : rows;
          return (
            <pre className="mono min-w-max py-2 text-[12px] leading-[1.6]">
              {shown.length === 0 && <div className="px-4 text-faint">no line matches “{filter}”</div>}
              {shown.map(({ line, n }) => {
                const hl = highlight && n >= highlight[0] && n <= highlight[1];
                const { className: _c, ...lp } = getLineProps({ line });
                return (
                  <div key={n} data-line={n} {...lp} className={cx("flex pr-4", hl && "bg-[var(--syn-hl)]")}>
                    <span className={cx("w-12 shrink-0 select-none pr-3 text-right tabular", hl ? "text-warn" : "text-faint")}>{n}</span>
                    <span className="whitespace-pre">
                      {line.map((token, key) => {
                        const { className: _t, ...tp } = getTokenProps({ token });
                        return <span key={key} {...tp} />;
                      })}
                    </span>
                  </div>
                );
              })}
            </pre>
          );
        }}
      </Highlight>
    </div>
  );
}

/** Fetches one dotted ref from /api/code and shows docstring + source. */
export function CodeRefView({ refName, maxH }: { refName: string; maxH?: number | string }) {
  const r = useFetch(`code:${refName}`, () => api.code(refName));
  if (r.loading && !r.data)
    return (
      <div className="flex items-center gap-2 p-3 text-muted">
        <Spinner /> loading {refName}
      </div>
    );
  if (r.error) return <ErrorBox>{r.error}</ErrorBox>;
  const c = r.data!;
  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="mono flex items-center gap-2 text-[11px] text-muted">
        <span className="text-fg">{c.file}</span>
        <span>
          :{c.start}–{c.end}
        </span>
        <span className="text-faint">({c.end - c.start + 1} lines)</span>
        <a className="ml-auto text-accent hover:underline" href={`#/code?module=${encodeURIComponent(c.ref.split(".").slice(0, 2).join("."))}&ref=${encodeURIComponent(c.ref)}`}>
          open in module ↗
        </a>
      </div>
      {c.doc && (
        <div className="rounded border-l-2 border-accent bg-accent-weak px-3 py-2 text-[12px] whitespace-pre-wrap text-fg">{c.doc}</div>
      )}
      <CodeBlock source={c.source} start={c.start} maxH={maxH} />
    </div>
  );
}

/** Tabs over every ref of a step. */
export function CodePanel({ refs }: { refs: string[] }) {
  const [sel, setSel] = useState(refs[0]);
  const key = refs.join(",");
  useEffect(() => setSel(refs[0]), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const current = useMemo(() => (refs.includes(sel) ? sel : refs[0]), [refs, sel]);
  if (!refs.length) return <div className="p-3 text-[12px] text-faint">This step has no code refs.</div>;
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {refs.map((r) => {
          const parts = r.split(".");
          const short = parts.slice(2).join(".") || r;
          return (
            <button
              key={r}
              title={r}
              onClick={() => setSel(r)}
              className={cx(
                "mono rounded border px-1.5 py-0.5 text-[11px]",
                r === current ? "border-accent bg-accent-weak text-accent" : "border-line text-muted hover:text-fg",
              )}
            >
              <span className="text-faint">{parts[1]}.</span>
              {short}
            </button>
          );
        })}
      </div>
      {current && <CodeRefView key={current} refName={current} maxH="calc(100vh - 260px)" />}
    </div>
  );
}
