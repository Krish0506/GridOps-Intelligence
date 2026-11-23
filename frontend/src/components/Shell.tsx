import { NavLink, Outlet } from "react-router-dom";

const nav = [
  { to: "/", label: "Operations Overview" },
  { to: "/assets", label: "Asset Explorer" },
  { to: "/predictive", label: "Predictive Analytics" },
  { to: "/risk", label: "Risk Prioritization" },
  { to: "/explainability", label: "Model Explainability" },
  { to: "/evidence", label: "Evidence Intelligence" },
  { to: "/decisions", label: "Engineering Decision Review" },
  { to: "/governance", label: "Governance and Audit" },
];

export default function Shell() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 bg-navy text-white p-4">
        <h1 className="text-lg font-bold mb-2">GridOps Intelligence</h1>
        <p className="text-xs text-teal mb-4">Synthetic demonstration data</p>
        <nav className="space-y-1">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `block px-3 py-2 rounded ${isActive ? "bg-slate text-white" : "text-slate-300 hover:bg-slate"}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6">
        <header className="mb-4">
          <p className="text-sm text-slate-500">Environment: local development · Synthetic data only</p>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
