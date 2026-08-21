import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Protocol, Site } from "../api/types";

export function SiteDetailPage() {
  const { siteId } = useParams<{ siteId: string }>();
  const navigate = useNavigate();
  const [site, setSite] = useState<Site | null>(null);
  const [protocols, setProtocols] = useState<Protocol[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    if (!siteId) return;
    api
      .getSite(siteId)
      .then(setSite)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load site"));
    api
      .listProtocolsForSite(siteId)
      .then(setProtocols)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load protocols"));
  }, [siteId]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!siteId) return;
    const form = new FormData(event.currentTarget);
    setError(null);
    try {
      const protocol = await api.createProtocol(siteId, {
        sponsor_name: String(form.get("sponsor")),
        protocol_number: String(form.get("number")),
        title: String(form.get("title")),
      });
      navigate(`/protocols/${protocol.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create protocol");
    }
  }

  return (
    <>
      <div className="breadcrumb">
        <Link to="/">Sites</Link> / {site?.name ?? "…"}
      </div>

      <div className="page-header">
        <div>
          <h1>{site?.name ?? "Loading…"}</h1>
          {site && (
            <p className="subtitle">
              {site.principal_investigator_name} · {site.contact_email}
            </p>
          )}
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ New protocol"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && (
        <form className="form-card" onSubmit={handleCreate}>
          <h2>New protocol</h2>
          <div className="field">
            <label htmlFor="sponsor">Sponsor</label>
            <input id="sponsor" name="sponsor" required placeholder="Acme Pharmaceuticals" />
          </div>
          <div className="field">
            <label htmlFor="number">Protocol number</label>
            <input id="number" name="number" required placeholder="ACM-204" />
          </div>
          <div className="field">
            <label htmlFor="title">Title</label>
            <input id="title" name="title" required placeholder="A Phase 2 Study of Compound X" />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              Create protocol
            </button>
          </div>
        </form>
      )}

      {protocols === null && !error && <p className="loading-line">Loading protocols…</p>}

      {protocols && protocols.length === 0 && (
        <div className="empty-state">No protocols at this site yet. Add the first one above.</div>
      )}

      {protocols && protocols.length > 0 && (
        <div className="card-list">
          {protocols.map((protocol) => (
            <Link key={protocol.id} to={`/protocols/${protocol.id}`} className="entity-card">
              <div className="title">{protocol.protocol_number}</div>
              <div className="meta">
                {protocol.sponsor_name} · {protocol.title}
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
