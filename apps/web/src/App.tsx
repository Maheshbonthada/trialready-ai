import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { SitesPage } from "./pages/SitesPage";
import { SiteDetailPage } from "./pages/SiteDetailPage";
import { ProtocolPage } from "./pages/ProtocolPage";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SitesPage />} />
        <Route path="/sites/:siteId" element={<SiteDetailPage />} />
        <Route path="/protocols/:protocolId" element={<ProtocolPage />} />
      </Routes>
    </Layout>
  );
}
