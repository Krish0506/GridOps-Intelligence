# Known Limitations

- Synthetic data only; not real-world utility performance.
- No authentication/authorization (production limitation).
- No frontend container in Docker Compose.
- PDF extraction is lightweight (no OCR).
- Anomaly scores are not calibrated probabilities.
- Ollama providers require a running Ollama instance (not auto-started).
- Single holdout-style split (no repeated cross-validation).