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
    checking: "border-amber-400/30 bg-amber-400/10 text-amber-100",
    connected: "border-emerald-400/30 bg-emerald-400/10 text-emerald-100",
    unavailable: "border-rose-400/30 bg-rose-400/10 text-rose-100",
  }[state];

  return <p className={`rounded-lg border px-4 py-3 text-sm ${tone}`}>{detail}</p>;
}
