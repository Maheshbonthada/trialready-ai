import { type DragEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { DocumentStatusPill } from "../components/DocumentStatusPill";
import { SeverityPill } from "../components/SeverityPill";
import type { BinderDocument, GapItem, GapReport, Protocol } from "../api/types";

const SEVERITY_ORDER: GapItem["severity"][] = [
  "missing",
  "expired",
  "outdated_version",
  "expiring_soon",
  "pending_review",
];
const SEVERITY_GROUP_LABEL: Record<GapItem["severity"], string> = {
  missing: "Missing documents",
  expired: "Expired documents",
  outdated_version: "Outdated versions",
  expiring_soon: "Expiring soon",
  pending_review: "Awaiting your review",
};

export function ProtocolPage() {
  const { protocolId } = useParams<{ protocolId: string }>();
  const [protocol, setProtocol] = useState<Protocol | null>(null);
  const [documents, setDocuments] = useState<BinderDocument[] | null>(null);
  const [report, setReport] = useState<GapReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [checkingGaps, setCheckingGaps] = useState(false);
  const [dragging, setDragging] = useState(false);

  const refresh = useCallback(() => {
    if (!protocolId) return;
    api.getProtocol(protocolId).then(setProtocol).catch(() => undefined);
    api.listDocuments(protocolId).then(setDocuments).catch(() => undefined);
    api.getLatestGapCheck(protocolId).then(setReport).catch(() => undefined);
  }, [protocolId]);

  useEffect(refresh, [refresh]);

  async function handleFiles(files: FileList | null) {
    if (!protocolId || !files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await api.uploadDocument(protocolId, file);
      }
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleRunGapCheck() {
    if (!protocolId) return;
    setCheckingGaps(true);
    setError(null);
    try {
      const result = await api.runGapCheck(protocolId);
      setReport(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gap check failed");
    } finally {
      setCheckingGaps(false);
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    handleFiles(event.dataTransfer.files);
  }

  const grouped = report
    ? SEVERITY_ORDER.map((severity) => ({
        severity,
        items: report.items.filter((item) => item.severity === severity),
      })).filter((group) => group.items.length > 0)
    : [];

  return (
    <>
      <div className="breadcrumb">
        <Link to="/">Sites</Link>
        {protocol && (
          <>
            {" "}
            / <Link to={`/sites/${protocol.site_id}`}>Protocols</Link> / {protocol.protocol_number}
          </>
        )}
      </div>

      <div className="page-header">
        <div>
          <h1>{protocol?.protocol_number ?? "Loading…"}</h1>
          {protocol && (
            <p className="subtitle">
              {protocol.sponsor_name} · {protocol.title}
            </p>
          )}
        </div>
        <button className="btn btn-secondary" onClick={handleRunGapCheck} disabled={checkingGaps}>
          {checkingGaps ? "Checking…" : "Run gap check"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <section>
        <h2>Regulatory binder</h2>
        <label
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            multiple
            onChange={(e) => handleFiles(e.target.files)}
            disabled={uploading}
          />
          {uploading ? "Uploading…" : "Drop binder documents here, or click to choose files"}
          <div className="hint">PDF, JPG, or PNG — one file per document</div>
        </label>

        {documents && documents.length > 0 && (
          <table className="doc-table" style={{ marginTop: "1rem" }}>
            <thead>
              <tr>
                <th>File</th>
                <th>Recognized as</th>
                <th>Status</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.original_filename}</td>
                  <td>{doc.document_type_id === "unclassified" ? "—" : doc.document_type_id}</td>
                  <td>
                    <DocumentStatusPill status={doc.status} />
                  </td>
                  <td className="tabular">{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>Monitor-visit readiness</h2>

        {!report && <p className="loading-line">Run a gap check to see readiness status.</p>}

        {report && (
          <>
            <div className={`readiness-banner ${report.is_monitor_visit_ready ? "ready" : "not-ready"}`}>
              <span>{report.is_monitor_visit_ready ? "✓ Ready for a monitor visit" : "Not ready yet"}</span>
              <span className="stat tabular">
                {report.total_satisfied} / {report.total_required} requirements clear
              </span>
            </div>

            {grouped.length === 0 ? (
              <div className="empty-state">Every required document is present and current.</div>
            ) : (
              grouped.map((group) => (
                <div className="gap-group" key={group.severity}>
                  <h3>{SEVERITY_GROUP_LABEL[group.severity]}</h3>
                  {group.items.map((item) => (
                    <div className="gap-item" key={item.document_type_id}>
                      <span className={`stripe ${item.severity}`} />
                      <div className="body">
                        <div className="name">
                          {item.document_name} <SeverityPill severity={item.severity} />
                        </div>
                        <div className="detail">{item.detail}</div>
                        <div className="basis">{item.regulatory_basis}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ))
            )}
          </>
        )}
      </section>
    </>
  );
}
