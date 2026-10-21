import { api, previewUrl, useFetch } from "../api";
import { Figure } from "../Figure";
import { DEFECTS, DOCS, DOC_LABEL, TIERS, TIER_INFO, TRAPS } from "../lib";
import { href, navigate, setParams, type Route } from "../router";
import type { Tier } from "../types";
import { Badge, ErrorBox, JsonBox, Section, Spinner, Tabs } from "../ui";

function CaseDetail({ caseId, tier }: { caseId: string; tier: Tier }) {
  const det = useFetch(`case:${tier}/${caseId}`, () => api.caseDetail(tier, caseId));
  const t = det.data?.truth;
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-3">
        <a className="text-[12px] text-accent hover:underline" href={href("dataset", { tier })}>
          ← all cases
        </a>
        <h2 className="mono text-[16px] font-semibold">{caseId}</h2>
        {t && (
          <span className="mono text-[12px] text-muted">
            Form A {t.layouts.form_a} · PoA {t.layouts.proof_of_address} · review date {t.as_of}
          </span>
        )}
        <button
          className="ml-auto h-8 rounded-md bg-accent px-3 text-[12px] font-semibold text-white dark:text-black"
          onClick={() => navigate("pipeline", { tier, case: caseId })}
        >
          Open in Pipeline ▸
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-2">
          <thead>
            <tr>
              <th className="w-28"></th>
              {TIERS.map((tr) => (
                <th key={tr} className="text-left font-medium">
                  <span className="mono">{tr}</span> <span className="text-[11px] font-normal text-muted">{TIER_INFO[tr]}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DOCS.map((d) => (
              <tr key={d}>
                <td className="align-top text-[12px] font-medium text-muted">{DOC_LABEL[d]}</td>
                {TIERS.map((tr) => (
                  <td key={tr} className="align-top">
                    <Figure src={previewUrl(tr, caseId, d, 900)} maxH={420} caption={`${tr}/${caseId}/${d}`} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {det.error && <ErrorBox>{det.error}</ErrorBox>}
      {!t && det.loading && <Spinner />}
      {t && (
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <Section title="Defects (must be flagged)">
              {t.defects.length === 0 ? (
                <div className="text-[12px] text-muted">None. This file should go straight through to pre-filled review.</div>
              ) : (
                t.defects.map((d) => (
                  <div key={d} className="flex items-start gap-2 py-0.5 text-[12px]">
                    <Badge mono tone="bad">
                      {d}
                    </Badge>
                    <span className="text-muted">{DEFECTS[d]}</span>
                  </div>
                ))
              )}
              <div className="mt-2 text-[11px] text-muted">
                expected_flags: <span className="mono">{JSON.stringify(t.expected_flags)}</span>
              </div>
            </Section>
            <Section title="Traps (harmless, must NOT be flagged)">
              {t.traps.length === 0 ? (
                <div className="text-[12px] text-faint">none</div>
              ) : (
                t.traps.map((d) => (
                  <div key={d} className="flex items-start gap-2 py-0.5 text-[12px]">
                    <Badge mono tone="warn">
                      {d}
                    </Badge>
                    <span className="text-muted">{TRAPS[d]}</span>
                  </div>
                ))
              )}
            </Section>
          </div>
          <Section title="truth.json">
            <JsonBox value={t} open={3} maxH={560} />
          </Section>
        </div>
      )}
    </div>
  );
}

export function DatasetPage({ route }: { route: Route }) {
  const tier = (TIERS.includes(route.params.tier as Tier) ? route.params.tier : "scan") as Tier;
  const cases = useFetch("cases", api.cases);
  if (route.params.case) return <div className="min-h-0 flex-1 overflow-auto"><CaseDetail caseId={route.params.case} tier={tier} /></div>;
  const list = (cases.data ?? []).filter((c) => c.tier === tier);
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-auto">
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-panel px-4 py-2.5">
        <Tabs tabs={TIERS.map((t) => ({ id: t, label: t }))} value={tier} onChange={(t) => setParams({ tier: t }, false)} />
        <span className="text-[12px] text-muted">{TIER_INFO[tier]}</span>
        <span className="ml-auto text-[12px] text-muted">
          {list.length} cases · {list.filter((c) => c.defects.length).length} with a defect
        </span>
      </div>
      {cases.error && <ErrorBox>{cases.error}</ErrorBox>}
      <div className="grid gap-3 p-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))" }}>
        {list.map((c) => (
          <a key={c.case} href={href("dataset", { tier, case: c.case })} className="flex flex-col gap-2 rounded-md border border-line bg-panel p-2 hover:border-accent">
            <div className="flex items-center gap-2">
              <span className="mono font-semibold">{c.case}</span>
              <span className="mono text-[11px] text-faint">
                A {c.layouts.form_a} · PoA {c.layouts.proof_of_address}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {DOCS.map((d) => (
                <div key={d} className="flex h-[150px] items-center justify-center overflow-hidden rounded border border-line bg-sunk">
                  <img loading="lazy" src={previewUrl(tier, c.case, d, 300)} alt={d} className="max-h-full max-w-full object-contain" />
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-1">
              {c.defects.length === 0 && <Badge tone="ok">no defect</Badge>}
              {c.defects.map((d) => (
                <Badge key={d} mono tone="bad" title={DEFECTS[d]}>
                  {d}
                </Badge>
              ))}
              {c.traps.map((d) => (
                <Badge key={d} mono tone="warn" title={TRAPS[d]}>
                  {d}
                </Badge>
              ))}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
