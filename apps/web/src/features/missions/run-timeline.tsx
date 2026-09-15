"use client";

import { useEffect, useRef, useState } from "react";

import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { streamRunEvents, type RunEventMessage } from "@/lib/api-client";

interface TimelineEntry {
  id: string;
  eventType: string;
  status: string | null;
  occurredAt: string | null;
  raw: unknown;
}

function parseEntry(message: RunEventMessage): TimelineEntry | null {
  try {
    const payload: unknown = JSON.parse(message.data);
    if (typeof payload !== "object" || payload === null) return null;
    const record = payload as Record<string, unknown>;
    return {
      id: message.id,
      eventType: typeof record.event_type === "string" ? record.event_type : "event",
      status: typeof record.status === "string" ? record.status : null,
      occurredAt: typeof record.timestamp === "string" ? record.timestamp : null,
      raw: payload,
    };
  } catch {
    return null;
  }
}

/** Live tail of a run's audit trail via SSE. Active only while the run is
 * still in flight -- the caller stops rendering this once the run reaches a
 * terminal state, since the stream has nothing further to say. */
export function RunTimeline({
  workspaceId,
  runId,
  active,
  onEvent,
}: {
  workspaceId: string;
  runId: string;
  active: boolean;
  onEvent?: () => void;
}) {
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    streamRunEvents(
      workspaceId,
      runId,
      (message) => {
        const entry = parseEntry(message);
        if (entry) setEntries((prev) => [...prev, entry].slice(-200));
        onEventRef.current?.();
      },
      controller.signal,
    ).catch(() => {
      // Connection dropped or was aborted -- the panel above already polls
      // run status independently, so this silently stops the live tail.
    });
    return () => controller.abort();
  }, [workspaceId, runId, active]);

  return (
    <Card>
      <CardHeading>Live timeline</CardHeading>
      <CardSubtext>
        {active ? "Streaming events for this run." : "This run has finished; showing its history."}
      </CardSubtext>
      <div className="mt-4 max-h-96 space-y-2 overflow-y-auto">
        {entries.length === 0 ? (
          <EmptyState>{active ? "Waiting for events..." : "No events were captured."}</EmptyState>
        ) : (
          entries
            .slice()
            .reverse()
            .map((entry) => (
              <div
                key={entry.id}
                className="rounded-md border border-line bg-paper px-3 py-2 text-sm"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xs text-ink">{entry.eventType}</span>
                  {entry.occurredAt ? (
                    <span className="text-xs text-ink-faint">
                      {new Date(entry.occurredAt).toLocaleTimeString()}
                    </span>
                  ) : null}
                </div>
                {entry.status ? <p className="mt-1 text-xs text-ink-muted">{entry.status}</p> : null}
              </div>
            ))
        )}
      </div>
    </Card>
  );
}
