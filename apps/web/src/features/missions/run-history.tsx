"use client";

import type { RunSummaryResponse } from "@aegisos/shared";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import { listMissionRuns, startRun } from "@/lib/api-client";

export function RunHistory({
  workspaceId,
  missionId,
  selectedRunId,
  onSelectRun,
  refreshToken,
  onRunStarted,
}: {
  workspaceId: string;
  missionId: string;
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  refreshToken: number;
  onRunStarted: () => void;
}) {
  const [runs, setRuns] = useState<RunSummaryResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    listMissionRuns(workspaceId, missionId)
      .then((rows) => {
        setRuns(rows);
        if (rows.length > 0 && !selectedRunId) onSelectRun(rows[0].id);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load run history");
      });
    // selectedRunId/onSelectRun intentionally excluded: this effect only
    // auto-selects the latest run on load/refresh, not on every selection.
  }, [workspaceId, missionId, refreshToken]);

  const runInFlight = runs?.some(
    (run) => !["completed", "failed", "cancelled"].includes(run.status),
  );

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const response = await startRun(workspaceId, missionId);
      onSelectRun(response.run_id);
      onRunStarted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  };

  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <div>
          <CardHeading>Runs</CardHeading>
          <CardSubtext>Every execution attempt for this mission.</CardSubtext>
        </div>
        <Button
          onClick={() => void handleStart()}
          disabled={starting || runInFlight}
          title={runInFlight ? "A run is already in progress" : undefined}
        >
          {starting ? "Starting..." : "Start run"}
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        {error ? <ErrorState message={error} /> : null}
        {!error && runs === null ? <LoadingState label="Loading runs..." /> : null}
        {!error && runs !== null && runs.length === 0 ? (
          <EmptyState>No runs yet. Start one to begin execution.</EmptyState>
        ) : null}
        {runs?.map((run) => (
          <button
            key={run.id}
            type="button"
            onClick={() => onSelectRun(run.id)}
            className={cn(
              "flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
              run.id === selectedRunId
                ? "border-cyan-400/50 bg-cyan-400/10"
                : "border-slate-700 bg-slate-800/30 hover:border-slate-600",
            )}
          >
            <span className="text-slate-300">{new Date(run.created_at).toLocaleString()}</span>
            <StatusBadge status={run.status} />
          </button>
        ))}
      </div>
    </Card>
  );
}
