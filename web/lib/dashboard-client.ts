"use client";

import { startTransition, useEffect, useRef, useState } from "react";

import {
  getDefaultDashboard,
  parseDashboardPayload,
  type DashboardData,
} from "@/lib/dashboard-schema";

type DashboardFetchState = {
  dashboard: DashboardData;
  error: string | null;
  isLoading: boolean;
  isRefreshing: boolean;
  lastLoadedAt: string | null;
};

type UseDashboardDataOptions = {
  intervalMs?: number;
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Failed to refresh dashboard data.";
}

export async function fetchDashboardFromApi(signal?: AbortSignal): Promise<DashboardData> {
  const response = await fetch(`/api/dashboard?_=${Date.now()}`, {
    cache: "no-store",
    headers: { accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Dashboard request failed with status ${response.status}`);
  }

  const payload = await response.json();
  return parseDashboardPayload(payload);
}

export function useDashboardData(
  { intervalMs = 60_000 }: UseDashboardDataOptions = {}
): DashboardFetchState {
  const [state, setState] = useState<DashboardFetchState>({
    dashboard: getDefaultDashboard(),
    error: null,
    isLoading: true,
    isRefreshing: false,
    lastLoadedAt: null,
  });
  const inFlightRef = useRef(false);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function refresh(background: boolean) {
      if (inFlightRef.current) return;
      inFlightRef.current = true;

      startTransition(() => {
        if (!mounted) return;
        setState((previous) => ({
          ...previous,
          error: background ? previous.error : null,
          isLoading: previous.lastLoadedAt === null && !background,
          isRefreshing: background || previous.lastLoadedAt !== null,
        }));
      });

      try {
        const dashboard = await fetchDashboardFromApi(controller.signal);
        if (!mounted) return;
        startTransition(() => {
          setState({
            dashboard,
            error: null,
            isLoading: false,
            isRefreshing: false,
            lastLoadedAt: new Date().toISOString(),
          });
        });
      } catch (error) {
        if (!mounted) return;
        if (controller.signal.aborted) return;
        startTransition(() => {
          setState((previous) => ({
            ...previous,
            error: getErrorMessage(error),
            isLoading: false,
            isRefreshing: false,
          }));
        });
      } finally {
        inFlightRef.current = false;
      }
    }

    void refresh(false);
    const timerId = window.setInterval(() => {
      void refresh(true);
    }, intervalMs);

    return () => {
      mounted = false;
      controller.abort();
      window.clearInterval(timerId);
    };
  }, [intervalMs]);

  return state;
}
