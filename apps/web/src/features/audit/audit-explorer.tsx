"use client";

import type { AuditEventResponse } from "@aegisos/shared";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { listAuditEvents } from "@/lib/api-client";

const PAGE_SIZE = 50;

export function AuditExplorer({ workspaceId }: { workspaceId: string }) {
  const [runIdFilter, setRunIdFilter] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [appliedFilters, setAppliedFilters] = useState({ runId: "", eventType: "" });
  const [offset, setOffset] = useState(0);
  const [events, setEvents] = useState<AuditEventResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAuditEvents(workspaceId, {
      runId: appliedFilters.runId || undefined,
      eventType: appliedFilters.eventType || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then(setEvents)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load audit events");
      });
  }, [workspaceId, appliedFilters, offset]);

  return (
    <Card>
      <CardHeading>Audit trail</CardHeading>
      <CardSubtext>Search every recorded agent invocation and workflow transition.</CardSubtext>
      <form
        className="mt-5 flex flex-wrap items-end gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setAppliedFilters({ runId: runIdFilter.trim(), eventType: eventTypeFilter.trim() });
        }}
      >
        <div>
          <Label htmlFor="filter-run-id">Run ID</Label>
          <Input
            id="filter-run-id"
            value={runIdFilter}
            onChange={(event) => setRunIdFilter(event.target.value)}
            placeholder="Filter by run"
            className="w-56"
          />
        </div>
        <div>
          <Label htmlFor="filter-event-type">Event type</Label>
          <Input
            id="filter-event-type"
            value={eventTypeFilter}
            onChange={(event) => setEventTypeFilter(event.target.value)}
            placeholder="e.g. execution.completed"
            className="w-56"
          />
        </div>
        <Button type="submit" variant="secondary">
          Apply filters
        </Button>
      </form>

      <div className="mt-5 space-y-2">
        {error ? <ErrorState message={error} /> : null}
        {!error && events === null ? <LoadingState label="Loading events..." /> : null}
        {!error && events !== null && events.length === 0 ? (
          <EmptyState>No audit events match these filters.</EmptyState>
        ) : null}
        {events?.map((event) => (
          <div
            key={event.id}
            className="rounded-lg border border-slate-700 bg-slate-800/30 px-3 py-2 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-xs text-cyan-300">{event.event_type}</span>
              <span className="text-xs text-slate-500">
                {new Date(event.occurred_at).toLocaleString()}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <Badge tone="neutral">{event.actor}</Badge>
              <span>run {event.run_id.slice(0, 8)}</span>
              <span>{event.status}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 flex items-center justify-between">
        <Button
          variant="secondary"
          disabled={offset === 0}
          onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          disabled={!events || events.length < PAGE_SIZE}
          onClick={() => setOffset((value) => value + PAGE_SIZE)}
        >
          Next
        </Button>
      </div>
    </Card>
  );
}
