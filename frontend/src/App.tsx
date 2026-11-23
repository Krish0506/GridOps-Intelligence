import { Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import Overview from "./pages/Overview";
import Assets from "./pages/Assets";
import Predictive from "./pages/Predictive";
import Risk from "./pages/Risk";
import Explainability from "./pages/Explainability";
import Evidence from "./pages/Evidence";
import Decisions from "./pages/Decisions";
import Governance from "./pages/Governance";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Overview />} />
        <Route path="assets" element={<Assets />} />
        <Route path="predictive" element={<Predictive />} />
        <Route path="risk" element={<Risk />} />
        <Route path="explainability" element={<Explainability />} />
        <Route path="evidence" element={<Evidence />} />
        <Route path="decisions" element={<Decisions />} />
        <Route path="governance" element={<Governance />} />
      </Route>
    </Routes>
  );
}
