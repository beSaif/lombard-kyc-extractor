import type { DocType, Tier } from "./types";

export const TIERS: Tier[] = ["clean", "scan", "photo"];
export const TIER_INFO: Record<Tier, string> = {
  clean: "Digital bill + crisp scans. The bill PDF has a text layer, so no OCR is needed for it.",
  scan: "Grey 150 dpi scans, slightly rotated, with noise. Everything goes through OCR.",
  photo: "Phone photos: perspective, shadow, blur. Needs flattening and light correction before OCR.",
};

export const DOCS: DocType[] = ["passport", "form_a", "proof_of_address"];
export const DOC_LABEL: Record<string, string> = {
  passport: "Passport",
  form_a: "Form A",
  proof_of_address: "Proof of address",
};

export const MODE_INFO: Record<string, string> = {
  text: "text: the model sees only the OCR / text-layer text, never the image.",
  vision: "vision: the model sees only the page images, no OCR text.",
  both: "both: the model sees the page images plus the OCR text as a hint.",
};

export const DEFECTS: Record<string, string> = {
  PASSPORT_EXPIRED: "Passport expired before the review date.",
  MRZ_CHECK_FAILED: "One MRZ check digit is wrong (ICAO 9303 7-3-1 checksum fails).",
  MRZ_VISUAL_MISMATCH: "Printed date of birth altered; the MRZ was left alone, so they disagree.",
  NAME_MISMATCH: "Bill is in a family member's name, not the passport holder's.",
  ADDRESS_MISMATCH: "Form A address and the bill's address are different places.",
  DOB_MISMATCH: "Day and month swapped on Form A versus the passport.",
  NATIONALITY_MISMATCH: "Form A nationality differs from the passport.",
  PROOF_OF_ADDRESS_TOO_OLD: "Bill is more than 90 days old on the review date.",
  SUSPICIOUS_INSTRUCTIONS: "Prompt injection hidden in the Form A remarks or the bill's fine print.",
};

export const TRAPS: Record<string, string> = {
  NAME_NO_MIDDLE: "Bill omits a middle name. Must not be flagged.",
  NAME_SURNAME_FIRST: 'Surname first, e.g. "MÜLLER Anna Maria".',
  NAME_NO_ACCENT: '"Muller" written for "Müller".',
  ADDR_ABBREVIATED: '"Av." for "Avenue", "str." for "strasse".',
  ADDR_CITY_ALIAS: "Geneva / Genève, a CH- postcode prefix.",
  ADDR_NUMBER_FIRST: '"12, rue des Exemples" (number before street).',
  POA_NEAR_LIMIT: "Bill is 80–89 days old; the limit is 90.",
  PASSPORT_EXPIRES_SOON: "Passport is valid but expires within 30 days.",
};

export const PROCESS_FLAGS: Record<string, string> = {
  EVIDENCE_NOT_FOUND: "A value could not be found on the page and nothing corroborates it.",
  MISSING_FIELD: "A required field was not extracted.",
  MISSING_DOCUMENT: "One of the three documents is missing.",
  MODEL_DISAGREEMENT: "Primary and second model disagree on a field.",
};

export const isDefect = (code: string) => code in DEFECTS;

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}
export function usd(v: number | null | undefined, digits = 5): string {
  if (v === null || v === undefined) return "–";
  return `$${v.toFixed(digits)}`;
}
export function ms(v: number | null | undefined): string {
  if (v === null || v === undefined) return "…";
  if (v >= 1000) return `${(v / 1000).toFixed(2)} s`;
  if (v >= 10) return `${v.toFixed(0)} ms`;
  return `${v.toFixed(1)} ms`;
}
export function num(v: number | null | undefined): string {
  if (v === null || v === undefined) return "–";
  return v.toLocaleString("en-US");
}
export function bytes(v: number): string {
  if (v > 1e6) return `${(v / 1e6).toFixed(2)} MB`;
  if (v > 1e3) return `${(v / 1e3).toFixed(1)} KB`;
  return `${v} B`;
}

export function cx(...a: (string | false | null | undefined)[]) {
  return a.filter(Boolean).join(" ");
}

export function prettyJSON(v: unknown): string {
  if (typeof v === "string") {
    try {
      return JSON.stringify(JSON.parse(v), null, 2);
    } catch {
      return v;
    }
  }
  return JSON.stringify(v, null, 2);
}

export const STATUS_COLOR: Record<string, string> = {
  verified: "var(--ok)",
  corroborated: "var(--info)",
  unverified: "var(--warn)",
  dropped: "var(--bad)",
};

export function confColor(c: number | null): string {
  if (c === null) return "var(--info)";
  if (c < 60) return "var(--bad)";
  if (c < 85) return "var(--warn)";
  return "var(--ok)";
}
