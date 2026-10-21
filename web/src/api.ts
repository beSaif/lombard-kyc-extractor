import { useEffect, useRef, useState } from "react";
import type {
  CaseDetail,
  CaseSummary,
  CodeRef,
  EvalReport,
  Extractor,
  ModuleSource,
  RunListItem,
  RunRequest,
  RunState,
} from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`);
  return r.json() as Promise<T>;
}

export const api = {
  cases: () => getJSON<CaseSummary[]>("/api/cases"),
  caseDetail: (tier: string, c: string) => getJSON<CaseDetail>(`/api/cases/${tier}/${c}`),
  extractors: () => getJSON<Extractor[]>("/api/extractors"),
  run: (id: string) => getJSON<RunState>(`/api/runs/${id}`),
  runs: () => getJSON<RunListItem[]>("/api/runs"),
  modules: () => getJSON<ModuleSource[]>("/api/modules"),
  evals: () => getJSON<EvalReport[]>("/api/evals"),
  code: (ref: string) => getJSON<CodeRef>(`/api/code?ref=${encodeURIComponent(ref)}`),
  startRun: async (req: RunRequest): Promise<{ run_id: string }> => {
    const r = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  },
};

export const previewUrl = (tier: string, c: string, doc: string, w = 900) =>
  `/api/preview/${tier}/${c}/${doc}?w=${w}`;

// Small cache so that switching between pages does not refetch static data.
const cache = new Map<string, Promise<unknown>>();
export function cached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  if (!cache.has(key)) {
    const p = fn().catch((e) => {
      cache.delete(key);
      throw e;
    });
    cache.set(key, p);
  }
  return cache.get(key) as Promise<T>;
}
export const invalidate = (key: string) => cache.delete(key);

export interface Loadable<T> {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
  reload: () => void;
}

/** Fetch once per key (cached). Pass key=null to skip. */
export function useFetch<T>(key: string | null, fn: () => Promise<T>, useCache = true): Loadable<T> {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: !!key });
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    if (!key) {
      setState({ loading: false });
      return;
    }
    let alive = true;
    setState((s) => ({ data: s.data, loading: true }));
    const p = useCache ? cached(key, fnRef.current) : fnRef.current();
    p.then(
      (data) => alive && setState({ data, loading: false }),
      (e: Error) => alive && setState({ error: e.message, loading: false }),
    );
    return () => {
      alive = false;
    };
  }, [key, tick, useCache]);
  return {
    ...state,
    error: state.error,
    reload: () => {
      if (key) invalidate(key);
      setTick((t) => t + 1);
    },
  } as Loadable<T>;
}

export function lsGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
export function lsSet(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode etc. */
  }
}
