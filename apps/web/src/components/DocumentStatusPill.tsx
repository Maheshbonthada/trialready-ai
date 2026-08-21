import type { DocumentStatus } from "../api/types";

const CONFIG: Record<DocumentStatus, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  accepted: { label: "Accepted", tone: "success" },
  pending_human_review: { label: "Needs review", tone: "warning" },
  pending_extraction: { label: "Processing…", tone: "neutral" },
  rejected: { label: "Rejected", tone: "danger" },
  superseded: { label: "Superseded", tone: "neutral" },
};

export function DocumentStatusPill({ status }: { status: DocumentStatus }) {
  const config = CONFIG[status];
  return <span className={`pill pill-${config.tone}`}>{config.label}</span>;
}
