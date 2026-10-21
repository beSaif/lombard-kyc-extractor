import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { cx } from "./lib";
import { CodePage } from "./pages/CodePage";
import { DatasetPage } from "./pages/Dataset";
import { EvalsPage } from "./pages/Evals";
import { PipelinePage } from "./pages/Pipeline";
import { href, useRoute } from "./router";

const PAGES = [
  { id: "pipeline", label: "Pipeline" },
  { id: "evals", label: "Evals" },
  { id: "dataset", label: "Dataset" },
  { id: "code", label: "Code" },
];

function App() {
  const route = useRoute();
  return (
    <div className="flex h-screen flex-col">
      <nav className="flex items-center gap-1 border-b border-line bg-panel px-4">
        <a href="#/pipeline" className="mr-4 flex items-center gap-2 py-2">
          <span className="mono rounded bg-accent px-1.5 py-0.5 text-[11px] font-bold text-white dark:text-black">KYC</span>
          <span className="font-semibold">Pipeline Lab</span>
          <span className="text-[11px] text-faint">passport · Form A · proof of address → fields + flags</span>
        </a>
        {PAGES.map((p) => (
          <a
            key={p.id}
            href={href(p.id)}
            className={cx(
              "border-b-2 px-3 py-2.5 text-[13px]",
              route.page === p.id ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg",
            )}
          >
            {p.label}
          </a>
        ))}
        <span className="mono ml-auto text-[11px] text-faint">api 127.0.0.1:8000</span>
      </nav>
      {route.page === "evals" ? (
        <EvalsPage route={route} />
      ) : route.page === "dataset" ? (
        <DatasetPage route={route} />
      ) : route.page === "code" ? (
        <CodePage route={route} />
      ) : (
        <PipelinePage route={route} />
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
