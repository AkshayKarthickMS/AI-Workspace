"use client";

import type { ArtifactResponse } from "@aegisos/shared";
import { useEffect, useState } from "react";

import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { downloadArtifactContent, getArtifactContent, listArtifacts } from "@/lib/api-client";

interface Slide {
  title: string;
  bullets: string[];
}

interface ReportContent {
  title?: string;
  executive_summary?: string;
  recommendations?: string[];
  qa_status?: string;
  compliance_verdict?: string;
  slide_deck?: { title?: string; slides?: Slide[] } | null;
}

function ReportViewer({ report }: { report: ReportContent }) {
  return (
    <div className="mt-4 space-y-4 border-t border-line pt-4">
      <div className="flex flex-wrap items-center gap-2">
        {report.qa_status ? <StatusBadge status={report.qa_status} /> : null}
        {report.compliance_verdict ? <StatusBadge status={report.compliance_verdict} /> : null}
      </div>
      {report.executive_summary ? (
        <p className="text-sm text-ink">{report.executive_summary}</p>
      ) : null}
      {report.recommendations && report.recommendations.length > 0 ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
            Recommendations
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
            {report.recommendations.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {report.slide_deck?.slides && report.slide_deck.slides.length > 0 ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
            {report.slide_deck.title ?? "Slide deck"}
          </p>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {report.slide_deck.slides.map((slide, index) => (
              <div key={index} className="rounded-md border border-line bg-paper p-3">
                <p className="text-sm font-medium text-ink">{slide.title}</p>
                <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs text-ink-muted">
                  {slide.bullets.map((bullet, bulletIndex) => (
                    <li key={bulletIndex}>{bullet}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ArtifactRow({ workspaceId, artifact }: { workspaceId: string; artifact: ArtifactResponse }) {
  const [expanded, setExpanded] = useState(false);
  const [content, setContent] = useState<ReportContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (content || artifact.artifact_type !== "report") return;
    setLoading(true);
    setError(null);
    try {
      const data = await getArtifactContent(workspaceId, artifact.id);
      setContent(data as ReportContent);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load artifact content");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-md border border-line bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Badge tone="info">{artifact.artifact_type}</Badge>
          <span className="text-xs text-ink-faint">
            {new Date(artifact.created_at).toLocaleString()}
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => void toggle()}>
            {expanded ? "Hide" : "View"}
          </Button>
          <Button
            variant="ghost"
            className="px-3 py-1.5 text-xs"
            onClick={() =>
              void downloadArtifactContent(
                workspaceId,
                artifact.id,
                `${artifact.artifact_type}-${artifact.id}.json`,
              )
            }
          >
            Download
          </Button>
        </div>
      </div>
      {expanded ? (
        loading ? (
          <LoadingState label="Loading content..." />
        ) : error ? (
          <ErrorState message={error} />
        ) : content ? (
          <ReportViewer report={content} />
        ) : null
      ) : null}
    </div>
  );
}

export function ArtifactsPanel({
  workspaceId,
  missionId,
  refreshKey,
}: {
  workspaceId: string;
  missionId: string;
  refreshKey: number;
}) {
  const [artifacts, setArtifacts] = useState<ArtifactResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listArtifacts(workspaceId, missionId)
      .then((rows) => {
        if (!cancelled) setArtifacts(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load artifacts");
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, missionId, refreshKey]);

  return (
    <Card>
      <CardHeading>Artifacts</CardHeading>
      <CardSubtext>Reports and slide decks produced by completed runs.</CardSubtext>
      <div className="mt-4 space-y-3">
        {error ? <ErrorState message={error} /> : null}
        {!error && artifacts === null ? <LoadingState label="Loading artifacts..." /> : null}
        {!error && artifacts !== null && artifacts.length === 0 ? (
          <EmptyState>No artifacts have been produced yet.</EmptyState>
        ) : null}
        {artifacts?.map((artifact) => (
          <ArtifactRow key={artifact.id} workspaceId={workspaceId} artifact={artifact} />
        ))}
      </div>
    </Card>
  );
}
