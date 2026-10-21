import { useState, type ReactNode } from "react";
import { cx } from "./lib";

type Tone = "neutral" | "accent" | "ok" | "info" | "warn" | "bad";

const toneCls: Record<Tone, string> = {
  neutral: "bg-sunk text-muted border-line",
  accent: "bg-accent-weak text-accent border-transparent",
  ok: "bg-ok-weak text-ok border-transparent",
  info: "bg-info-weak text-info border-transparent",
  warn: "bg-warn-weak text-warn border-transparent",
  bad: "bg-bad-weak text-bad border-transparent",
};

export function Badge({
  children,
  tone = "neutral",
  mono = false,
  title,
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  mono?: boolean;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-[1px] text-[11px] leading-[16px] whitespace-nowrap",
        mono && "mono",
        toneCls[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export const statusTone = (s: string | undefined | null): Tone =>
  s === "verified" ? "ok" : s === "corroborated" ? "info" : s === "unverified" ? "warn" : s === "dropped" ? "bad" : "neutral";

export function StatusBadge({ status }: { status: string | undefined | null }) {
  return <Badge tone={statusTone(status)}>{status ?? "–"}</Badge>;
}

/** ✓ / ✗ / – for passed / failed / skipped. */
export function PassMark({ passed, size = 14 }: { passed: boolean | null | undefined; size?: number }) {
  if (passed === true)
    return (
      <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-ok-weak text-ok font-bold" style={{ width: size + 4, height: size + 4, fontSize: size - 3 }}>
        ✓
      </span>
    );
  if (passed === false)
    return (
      <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-bad-weak text-bad font-bold" style={{ width: size + 4, height: size + 4, fontSize: size - 3 }}>
        ✗
      </span>
    );
  return (
    <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-sunk text-faint" style={{ width: size + 4, height: size + 4, fontSize: size - 3 }} title="skipped">
      –
    </span>
  );
}

export function Spinner({ size = 12 }: { size?: number }) {
  return (
    <span
      className="spin inline-block shrink-0 rounded-full border-2 border-line-strong border-t-accent"
      style={{ width: size, height: size }}
    />
  );
}

export function Section({
  title,
  right,
  children,
  className,
  pad = true,
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  pad?: boolean;
}) {
  return (
    <section className={cx("rounded-md border border-line bg-panel", className)}>
      {title !== undefined && (
        <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-1.5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">{title}</h3>
          {right}
        </header>
      )}
      <div className={pad ? "p-3" : ""}>{children}</div>
    </section>
  );
}

export function KV({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <table className="dt">
      <tbody>
        {rows.map(([k, v], i) => (
          <tr key={i}>
            <td className="w-[1%] whitespace-nowrap text-muted">{k}</td>
            <td className="mono break-all">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Pre({ children, className, maxH = 420 }: { children: ReactNode; className?: string; maxH?: number | null }) {
  return (
    <pre
      className={cx("mono overflow-auto rounded border border-line bg-code p-2.5 text-[12px] leading-[1.55] whitespace-pre-wrap break-words", className)}
      style={maxH ? { maxHeight: maxH } : undefined}
    >
      {children}
    </pre>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  size = "md",
}: {
  tabs: { id: T; label: ReactNode; title?: string }[];
  value: T;
  onChange: (v: T) => void;
  size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex rounded-md border border-line bg-sunk p-0.5">
      {tabs.map((t) => (
        <button
          key={t.id}
          title={t.title}
          onClick={() => onChange(t.id)}
          className={cx(
            "rounded px-2.5 transition-colors",
            size === "sm" ? "py-0.5 text-[12px]" : "py-1 text-[13px]",
            value === t.id ? "bg-panel text-fg shadow-sm font-medium" : "text-muted hover:text-fg",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="inline-flex cursor-pointer select-none items-center gap-1.5 text-[12px] text-muted">
      <input type="checkbox" className="accent-[var(--accent)]" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-6 text-center text-[12px] text-faint">{children}</div>;
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return <div className="mono rounded border border-bad/40 bg-bad-weak p-2 text-[12px] text-bad whitespace-pre-wrap">{children}</div>;
}

/** Collapsible JSON tree. */
export function JsonTree({ value, name, depth = 0, open = 2 }: { value: unknown; name?: string; depth?: number; open?: number }) {
  const [expanded, setExpanded] = useState(depth < open);
  const label = name !== undefined ? <span className="text-info">{JSON.stringify(name)}</span> : null;
  if (value === null || typeof value !== "object") {
    const cls =
      typeof value === "string" ? "text-[var(--syn-str)]" : typeof value === "number" ? "text-[var(--syn-num)]" : "text-[var(--syn-kw)]";
    return (
      <div className="pl-4">
        {label}
        {label && <span className="text-faint">: </span>}
        <span className={cls}>{JSON.stringify(value)}</span>
      </div>
    );
  }
  const isArr = Array.isArray(value);
  const entries = isArr ? (value as unknown[]).map((v, i) => [String(i), v] as const) : Object.entries(value as object);
  const [o, c] = isArr ? ["[", "]"] : ["{", "}"];
  return (
    <div className={depth ? "pl-4" : ""}>
      <button className="-ml-4 w-4 text-faint hover:text-fg" onClick={() => setExpanded(!expanded)}>
        {expanded ? "▾" : "▸"}
      </button>
      {label}
      {label && <span className="text-faint">: </span>}
      <span className="text-faint">{o}</span>
      {!expanded && (
        <button className="text-faint hover:text-fg" onClick={() => setExpanded(true)}>
          {" "}
          {entries.length} {isArr ? "items" : "keys"} {c}
        </button>
      )}
      {expanded && (
        <>
          {entries.map(([k, v]) => (
            <JsonTree key={k} name={isArr ? undefined : k} value={v} depth={depth + 1} open={open} />
          ))}
          <div className="text-faint">{c}</div>
        </>
      )}
    </div>
  );
}

export function JsonBox({ value, open = 2, maxH = 420 }: { value: unknown; open?: number; maxH?: number }) {
  return (
    <div className="mono overflow-auto rounded border border-line bg-code py-2 pr-2 pl-5 text-[12px] leading-[1.55]" style={{ maxHeight: maxH }}>
      <JsonTree value={value} open={open} />
    </div>
  );
}

export function Bar({ value, max = 100, threshold, color }: { value: number | null; max?: number; threshold?: number; color?: string }) {
  const w = value === null ? 0 : Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <div className="relative h-2 w-16 rounded-sm bg-sunk border border-line">
      <div className="h-full rounded-sm" style={{ width: `${w}%`, background: color ?? "var(--accent)" }} />
      {threshold !== undefined && (
        <div className="absolute -top-1 -bottom-1 w-px bg-fg" style={{ left: `${(threshold / max) * 100}%` }} title={`threshold ${threshold}`} />
      )}
    </div>
  );
}

export function Collapsible({ title, children, defaultOpen = false, right }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean; right?: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-md border border-line bg-panel">
      <header className="flex items-center justify-between gap-2 px-3 py-1.5">
        <button className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted hover:text-fg" onClick={() => setOpen(!open)}>
          <span className="w-3 text-faint">{open ? "▾" : "▸"}</span>
          {title}
        </button>
        {right}
      </header>
      {open && <div className="border-t border-line p-3">{children}</div>}
    </section>
  );
}
