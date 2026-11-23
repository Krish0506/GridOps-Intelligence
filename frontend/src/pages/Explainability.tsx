export default function Explainability() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Model Explainability</h2>
      <div className="bg-white p-4 rounded shadow">
        <p>
          Explanations are based on feature deviation ranking (robust z-scores) and
          global feature importance. This is not SHAP and does not imply causality.
        </p>
        <p className="text-sm text-slate-500 mt-2">
          Prediction cutoff and data quality warnings are shown per asset in Risk
          Prioritization.
        </p>
      </div>
    </div>
  );
}
