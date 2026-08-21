import type { GapSeverity } from "../api/types";

const LABELS: Record<GapSeverity, string> = {
  missing: "Missing",
  expired: "Expired",
  expiring_soon: "Expiring soon",
  outdated_version: "Outdated version",
  pending_review: "Pending review",
};

// Only "missing" / "expired" / "outdated_version" block monitor-visit readiness
// (see GapReport.is_monitor_visit_ready server-side) — the pill tone follows
// that same distinction so the visual severity never contradicts what the
// readiness banner says.
const TONE: Record<GapSeverity, "danger" | "warning"> = {
  missing: "danger",
  expired: "danger",
  outdated_version: "danger",
  expiring_soon: "warning",
  pending_review: "warning",
};

export function SeverityPill({ severity }: { severity: GapSeverity }) {
  return <span className={`pill pill-${TONE[severity]}`}>{LABELS[severity]}</span>;
}
