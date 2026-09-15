"use client";

import type { RunDetailResponse } from "@aegisos/shared";
import { useCallback, useEffect, useState } from "react";

import { Badge, StatusBadge } from "@/components/ui/badge";
import { Card, CardHeading } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { getRun } from "@/lib/api-client";

import { ApprovalPanel } from "./approval-panel";
import { ArtifactsPanel } from "./artifacts-panel";
import { PlanView } from "./plan-view";
import { RunTimeline } from "./run-timeline";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);
const POLL_INTERVAL_MS = 4000;

function ResultSummary({
  label,
  result,
}: {
  label: string;
  result: Record<string, unknown> | null | undefined;
}) {
  if (!result) return null;
  const status =
    typeof result.status === "string"
      ? result.status
      : typeof result.verdict === "string"
        ? result.verdict
        : null;
  return (
    <div className="flex items-center gap-2 text-sm text-ink">
      <span className="text-ink-muted">{label}</span>
      {status ? <StatusBadge status={status} /> : <Badge tone="neutral">recorded</Badge>}
    </div>
  );
}

export function RunPanel({
  workspaceId,
  missionId,
  runId,
  onMissionChanged,
}: {
  workspaceId: string;
  missionId: string;
  runId: string;
  onMissionChanged: () => void;
}) {
  const [detail, setDetail] = useState<RunDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [artifactsRefresh, setArtifactsRefresh] = useState(0);

  const refresh = useCallback(() => {
    getRun(workspaceId, runId)
      .then((data) => {
        setDetail((previous) => {
          if (previous && TERMINAL_STATUSES.has(previous.status) && previous.status !== data.status) {
            setArtifactsRefresh((token) => token + 1);
          }
          return data;
        });
        setError(null);
      })
      .catch((err: unknown) => {
        // A run that was *just* started can 404 for a moment -- the 202
        // response returns before the background task has written its first
        // checkpoint. Only surface an error once we've never managed to load
        // this run at all; otherwise keep the last known-good detail on
        // screen and let the next poll tick try again.
        setError((previous) =>
          previous === null && detail === null
            ? err instanceof Error
              ? err.message
              : "Failed to load run detail"
            : previous,
        );
      });
  }, [workspaceId, runId, detail]);

  useEffect(() => {
    setDetail(null);
    setError(null);
    refresh();
    // Only re-run when the run identity changes -- refresh's own identity
    // changes every render (it closes over `detail`), which would otherwise
    // reset the view on every successful poll.
  }, [workspaceId, runId]);

  // Keep polling until we've successfully loaded the run at least once, or
  // until it reaches a terminal status -- not just while `detail` happens to
  // already be set, so a start-run race that 404s briefly still recovers on
  // its own instead of freezing on the initial error.
  const active = !detail || !TERMINAL_STATUSES.has(detail.status);

  useEffect(() => {
    if (!active) return;
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [active, refresh]);

  const status = detail?.status;
  useEffect(() => {
    if (status && TERMINAL_STATUSES.has(status)) onMissionChanged();
    // Runs once per status value change rather than on every parent render
    // -- re-invoking onMissionChanged again for the same terminal status
    // would just be a harmless, idempotent extra refresh.
  }, [status]);

  if (!detail && error) return <ErrorState message={error} />;
  if (!detail) return <LoadingState label="Loading run..." />;

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardHeading>Run status</CardHeading>
          <StatusBadge status={detail.status} />
        </div>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
          <ResultSummary label="QA" result={detail.qa_result} />
          <ResultSummary label="Compliance" result={detail.compliance_result} />
        </div>
        {detail.last_error ? (
          <div className="mt-4">
            <ErrorState
              message={
                typeof detail.last_error.message === "string"
                  ? detail.last_error.message
                  : "The run encountered an error."
              }
            />
          </div>
        ) : null}
      </Card>

      <ApprovalPanel
        workspaceId={workspaceId}
        runId={runId}
        status={detail.status}
        approval={detail.approval}
        escalation={detail.escalation}
        onResolved={refresh}
      />

      <PlanView plan={detail.plan} tasks={detail.tasks} />

      <RunTimeline workspaceId={workspaceId} runId={runId} active={active} onEvent={refresh} />

      <ArtifactsPanel workspaceId={workspaceId} missionId={missionId} refreshKey={artifactsRefresh} />
    </div>
  );
}
