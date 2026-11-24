import { useEffect } from "react";
import type { ReactElement, SVGProps } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  IconAsset,
  IconChart,
  IconDecision,
  IconEvidence,
  IconExplain,
  IconGovernance,
  IconGrid,
  IconPulse,
  IconRisk,
} from "./Icons";
import { Badge } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: (props: SVGProps<SVGSVGElement>) => ReactElement;
  end?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "Command center",
    items: [{ to: "/", label: "Operations Overview", icon: IconGrid, end: true }],
  },
  {
    label: "Asset intelligence",
    items: [
      { to: "/assets", label: "Asset Explorer", icon: IconAsset },
      { to: "/predictive", label: "Predictive Analytics", icon: IconChart },
      { to: "/risk", label: "Risk Prioritization", icon: IconRisk },
      { to: "/explainability", label: "Model Explainability", icon: IconExplain },
    ],
  },
  {
    label: "Evidence & action",
    items: [
      { to: "/evidence", label: "Evidence Intelligence", icon: IconEvidence },
      { to: "/decisions", label: "Engineering Decision Review", icon: IconDecision },
    ],
  },
  {
    label: "Trust & lineage",
    items: [{ to: "/governance", label: "Governance and Audit", icon: IconGovernance }],
  },
];

export default function Shell() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [location.pathname]);

  return (
    <div className="min-h-screen">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col bg-gradient-to-b from-navy-950 via-navy-900 to-navy-800 lg:flex">
        <div className="flex items-center gap-3 px-6 py-6">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-400 to-teal-600 text-navy-950 shadow-lg shadow-teal-500/20">
            <IconPulse className="h-6 w-6" strokeWidth={2} />
          </div>
          <div>
            <p className="text-[15px] font-semibold tracking-tight text-white">GridOps Intelligence</p>
            <p className="text-[11px] text-slate-400">Asset decision support</p>
          </div>
        </div>

        <div className="mx-4 mb-4 rounded-xl border border-white/10 bg-white/5 px-3.5 py-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-teal-300">Environment</span>
            <span className="flex items-center gap-1.5 text-[10px] font-medium text-slate-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Local
            </span>
          </div>
          <p className="mt-1.5 text-[11px] leading-4 text-slate-400">Synthetic demonstration data. Not production utility data.</p>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-4 pb-4">
          {navGroups.map((group) => (
            <div key={group.label}>
              <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{group.label}</p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) => `nav-link group ${isActive ? "nav-link-active" : ""}`}
                    >
                      {({ isActive }) => (
                        <>
                          <span
                            className={`flex h-7 w-7 items-center justify-center rounded-lg transition ${
                              isActive ? "bg-teal-400/20 text-teal-300" : "text-slate-400 group-hover:text-slate-200"
                            }`}
                          >
                            <Icon className="h-4 w-4" />
                          </span>
                          <span className="flex-1 leading-4">{item.label}</span>
                          {isActive && <span className="h-1.5 w-1.5 rounded-full bg-teal-300" />}
                        </>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2.5">
            <div>
              <p className="text-[11px] font-medium text-slate-200">PostgreSQL + FastAPI</p>
              <p className="text-[10px] text-slate-500">Live local warehouse</p>
            </div>
            <Badge tone="navy">DEMO</Badge>
          </div>
          <a
            className="mt-2 block px-3 text-[11px] text-slate-500 transition hover:text-teal-300"
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            Open API documentation →
          </a>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 border-b border-ink-300/60 bg-white/85 backdrop-blur">
          <div className="flex items-center justify-between gap-4 px-4 py-3.5 md:px-8">
            <div className="flex items-center gap-3 lg:hidden">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-navy-900 text-teal-300">
                <IconPulse className="h-5 w-5" />
              </div>
              <span className="text-sm font-semibold text-ink-900">GridOps Intelligence</span>
            </div>
            <div className="hidden items-center gap-2 text-xs text-ink-500 lg:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Local development environment
              <span className="mx-1 text-ink-300">/</span>
              Synthetic data only
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="teal">Human-in-the-loop</Badge>
              <Badge tone="slate">M1–M11</Badge>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-ink-300/50 px-3 py-2 lg:hidden" aria-label="Mobile navigation">
            {navGroups.flatMap((group) => group.items).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium ${
                    isActive ? "bg-navy-900 text-white" : "text-ink-500 hover:bg-ink-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main id="main-content" className="mx-auto max-w-[1500px] px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>

        <footer className="mx-auto max-w-[1500px] px-4 pb-8 pt-2 text-[11px] leading-5 text-ink-500 md:px-8">
          GridOps Intelligence · Synthetic demonstration platform · Model outputs and anomaly scores are not real-world failure probabilities.
        </footer>
      </div>
    </div>
  );
}
