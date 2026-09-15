"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api-client";

type ConnectionState = "checking" | "connected" | "unavailable";

export function HealthStatus() {
  const [state, setState] = useState<ConnectionState>("checking");
  const [detail, setDetail] = useState("Checking API connection...");

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => {
        setState("connected");
        setDetail(`API connected - ${health.service} v${health.version}`);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setState("unavailable");
          setDetail("API unavailable. Start the local stack to enable this connection.");
        }
      });
    return () => controller.abort();
  }, []);

  const tone = {
    checking: "border-amber-200 bg-amber-50 text-amber-900",
    connected: "border-emerald-200 bg-emerald-50 text-emerald-900",
    unavailable: "border-red-200 bg-red-50 text-red-900",
  }[state];

  return <p className={`rounded-md border px-4 py-3 text-sm ${tone}`}>{detail}</p>;
}
