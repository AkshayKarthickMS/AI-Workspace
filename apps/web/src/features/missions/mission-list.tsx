"use client";

import type { MissionResponse } from "@aegisos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { listMissions } from "@/lib/api-client";

export function MissionList({ workspaceId }: { workspaceId: string }) {
  const [missions, setMissions] = useState<MissionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setMissions(null);
    setError(null);
    listMissions(workspaceId)
      .then((rows) => {
        if (!cancelled) setMissions(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load missions");
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Missions</h2>
        <Link href="/missions/new">
          <Button>New mission</Button>
        </Link>
      </div>
      {error ? <ErrorState message={error} /> : null}
      {!error && missions === null ? <LoadingState label="Loading missions..." /> : null}
      {!error && missions !== null && missions.length === 0 ? (
        <EmptyState>No missions yet. Create one to get started.</EmptyState>
      ) : null}
      {missions && missions.length > 0 ? (
        <ul className="space-y-3">
          {missions.map((mission) => (
            <li key={mission.id}>
              <Link href={`/missions/${mission.id}`}>
                <Card className="transition-colors hover:border-cyan-400/40">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-white">{mission.title}</p>
                      <p className="mt-1 truncate text-sm text-slate-400">{mission.raw_request}</p>
                    </div>
                    <StatusBadge status={mission.status} />
                  </div>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
