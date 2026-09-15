"use client";

import type { MissionResponse } from "@aegisos/shared";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useWorkspace } from "@/features/workspace/workspace-context";
import { RunHistory } from "@/features/missions/run-history";
import { RunPanel } from "@/features/missions/run-panel";
import { getMission } from "@/lib/api-client";

export default function MissionDetailPage() {
  const params = useParams<{ missionId: string }>();
  const missionId = params.missionId;
  const { currentWorkspaceId } = useWorkspace();

  const [mission, setMission] = useState<MissionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runsRefreshToken, setRunsRefreshToken] = useState(0);

  const loadMission = useCallback(() => {
    if (!currentWorkspaceId) return;
    getMission(currentWorkspaceId, missionId)
      .then(setMission)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load mission");
      });
  }, [currentWorkspaceId, missionId]);

  useEffect(() => {
    loadMission();
  }, [loadMission]);

  if (!currentWorkspaceId) return <LoadingState label="Loading workspace..." />;
  if (error) return <ErrorState message={error} />;
  if (!mission) return <LoadingState label="Loading mission..." />;

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardHeading>{mission.title}</CardHeading>
            <CardSubtext>{mission.raw_request}</CardSubtext>
          </div>
          <StatusBadge status={mission.status} />
        </div>
      </Card>

      <RunHistory
        workspaceId={currentWorkspaceId}
        missionId={missionId}
        selectedRunId={selectedRunId}
        onSelectRun={setSelectedRunId}
        refreshToken={runsRefreshToken}
        onRunStarted={() => setRunsRefreshToken((token) => token + 1)}
      />

      {selectedRunId ? (
        <RunPanel
          key={selectedRunId}
          workspaceId={currentWorkspaceId}
          missionId={missionId}
          runId={selectedRunId}
          onMissionChanged={() => {
            loadMission();
            setRunsRefreshToken((token) => token + 1);
          }}
        />
      ) : null}
    </div>
  );
}
