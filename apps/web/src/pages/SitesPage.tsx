import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Site } from "../api/types";

export function SitesPage() {
  const [sites, setSites] = useState<Site[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .listSites()
      .then(setSites)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load sites"));
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    try {
      const site = await api.createSite({
        name: String(form.get("name")),
        principal_investigator_name: String(form.get("pi")),
        contact_email: String(form.get("email")),
      });
      navigate(`/sites/${site.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create site");
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Sites</h1>
          <p className="subtitle">Every site you coordinate regulatory binders for.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ New site"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && (
        <form className="form-card" onSubmit={handleCreate}>
          <h2>New site</h2>
          <div className="field">
            <label htmlFor="name">Site name</label>
            <input id="name" name="name" required placeholder="Riverside Clinical Research" />
          </div>
          <div className="field">
            <label htmlFor="pi">Principal investigator</label>
            <input id="pi" name="pi" required placeholder="Dr. Amara Okafor" />
          </div>
          <div className="field">
            <label htmlFor="email">Coordinator email</label>
            <input id="email" name="email" type="email" required placeholder="coordinator@site.example" />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              Create site
            </button>
          </div>
        </form>
      )}

      {sites === null && !error && <p className="loading-line">Loading sites…</p>}

      {sites && sites.length === 0 && (
        <div className="empty-state">No sites yet. Add the first one above.</div>
      )}

      {sites && sites.length > 0 && (
        <div className="card-list">
          {sites.map((site) => (
            <Link key={site.id} to={`/sites/${site.id}`} className="entity-card">
              <div className="title">{site.name}</div>
              <div className="meta">
                {site.principal_investigator_name} · {site.contact_email}
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
