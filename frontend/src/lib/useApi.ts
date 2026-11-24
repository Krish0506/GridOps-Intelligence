import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet } from "./api";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** Fetch JSON through the Vite proxy with loading, error, and retry state. */
export function useApi<T>(path: string | null, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(path));
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const latest = useRef(0);

  const reload = useCallback(() => setVersion((current) => current + 1), []);

  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const requestId = latest.current + 1;
    latest.current = requestId;
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiGet<T>(path)
      .then((payload) => {
        if (!cancelled && latest.current === requestId) {
          setData(payload);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled && latest.current === requestId) {
          setError(cause instanceof Error ? cause.message : "Request failed");
        }
      })
      .finally(() => {
        if (!cancelled && latest.current === requestId) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, version, ...deps]);

  return { data, loading, error, reload };
}
