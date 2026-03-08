import { useState, useEffect, useCallback } from "react";

/**
 * Auto-refresh hook that triggers a re-render at a given interval.
 * Returns a tick counter and a formatted "last refreshed" string.
 */
export function useLiveRefresh(intervalMs: number = 30000) {
  const [tick, setTick] = useState(0);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setTick(t => t + 1);
      setLastRefresh(new Date());
    }, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);

  const refreshedAgo = useCallback(() => {
    const diff = Math.floor((Date.now() - lastRefresh.getTime()) / 1000);
    if (diff < 5) return "just now";
    if (diff < 60) return `${diff}s ago`;
    return `${Math.floor(diff / 60)}m ago`;
  }, [lastRefresh]);

  return { tick, lastRefresh, refreshedAgo };
}

/**
 * Returns a relative time string that updates every minute.
 */
export function useRelativeTime(timestamp: string | Date) {
  const [, setTick] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(timer);
  }, []);

  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
