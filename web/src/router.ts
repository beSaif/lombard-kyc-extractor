import { useEffect, useState } from "react";

// Hash routing: #/pipeline?tier=photo&case=case_001&extractor=rules&run=...

export interface Route {
  page: string;
  params: Record<string, string>;
}

function parse(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  const [path, qs] = h.split("?");
  const params: Record<string, string> = {};
  new URLSearchParams(qs || "").forEach((v, k) => (params[k] = v));
  return { page: path || "pipeline", params };
}

function build(page: string, params: Record<string, string | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") q.set(k, v);
  const s = q.toString();
  return `#/${page}${s ? "?" + s : ""}`;
}

export function useRoute(): Route {
  const [r, setR] = useState(parse);
  useEffect(() => {
    const on = () => setR(parse());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}

export function navigate(page: string, params: Record<string, string | null | undefined> = {}) {
  window.location.hash = build(page, params);
}

export function href(page: string, params: Record<string, string | null | undefined> = {}) {
  return build(page, params);
}

/** Merge params into the current route. replace=true does not add a history entry. */
export function setParams(patch: Record<string, string | null | undefined>, replace = true) {
  const cur = parse();
  const next = build(cur.page, { ...cur.params, ...patch });
  if (replace) {
    window.history.replaceState(null, "", next);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = next;
  }
}
