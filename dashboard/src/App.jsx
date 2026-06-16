import React, { useEffect, useState } from "react";
import Sidebar, { NAV } from "./components/Sidebar.jsx";
import { ToastProvider } from "./hooks/useToast.jsx";
import { api, SAMPLE, withFallback } from "./api/client.js";
import Overview from "./pages/Overview.jsx";
import RepositoryMap from "./pages/RepositoryMap.jsx";
import StalenessReport from "./pages/StalenessReport.jsx";
import PRActivity from "./pages/PRActivity.jsx";
import LiveConsole from "./pages/LiveConsole.jsx";
import Configuration from "./pages/Configuration.jsx";

const PAGES = {
  overview: Overview,
  map: RepositoryMap,
  staleness: StalenessReport,
  prs: PRActivity,
  console: LiveConsole,
  config: Configuration,
};

export default function App() {
  const [active, setActive] = useState("overview");
  const [health, setHealth] = useState("green");

  useEffect(() => {
    withFallback(api.overview, SAMPLE.overview).then((d) => setHealth(d.health));
  }, []);

  // Keyboard navigation: Alt+1..6 jump between sections.
  useEffect(() => {
    const onKey = (e) => {
      if (e.altKey && e.key >= "1" && e.key <= String(NAV.length)) {
        setActive(NAV[Number(e.key) - 1].id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const Page = PAGES[active];
  const index = NAV.findIndex((n) => n.id === active);

  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar active={active} onChange={setActive} health={health} />
        <main className="flex-1 overflow-y-auto px-6 py-9 md:px-12">
          <div className="mx-auto max-w-6xl">
            {/* keyed wrapper -> guiding page transition on every section change */}
            <div key={active} className="animate-page-in">
              <div className="mb-5 flex items-center gap-3 text-[10px] font-semibold uppercase tracking-label text-paper-400">
                <span className="font-mono text-clay">{String(index + 1).padStart(2, "0")}</span>
                <span className="h-px w-8 bg-paper-50/20" />
                <span>DocPilot Control</span>
              </div>
              <Page />
            </div>
          </div>
        </main>
      </div>
    </ToastProvider>
  );
}
