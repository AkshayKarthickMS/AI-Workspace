"use client";

import type { KnowledgeDocumentResponse } from "@aegisos/shared";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { ingestKnowledgeDocument, listKnowledgeDocuments } from "@/lib/api-client";

function IngestForm({ workspaceId, onIngested }: { workspaceId: string; onIngested: () => void }) {
  const [sourceUri, setSourceUri] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <Card>
      <CardHeading>Ingest a document</CardHeading>
      <CardSubtext>
        Paste text content and a source identifier. Ingestion runs immediately and is audited.
      </CardSubtext>
      <form
        className="mt-5 flex flex-col gap-4"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!sourceUri.trim() || !text.trim() || submitting) return;
          setSubmitting(true);
          setError(null);
          try {
            await ingestKnowledgeDocument(workspaceId, {
              source_uri: sourceUri.trim(),
              text,
            });
            setSourceUri("");
            setText("");
            onIngested();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to ingest document");
          } finally {
            setSubmitting(false);
          }
        }}
      >
        <div>
          <Label htmlFor="source-uri">Source</Label>
          <Input
            id="source-uri"
            value={sourceUri}
            onChange={(event) => setSourceUri(event.target.value)}
            placeholder="e.g. policy://refund-guidelines-v2"
            required
          />
        </div>
        <div>
          <Label htmlFor="doc-text">Content</Label>
          <Textarea
            id="doc-text"
            rows={6}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste the document text to ingest"
            required
          />
        </div>
        {error ? <ErrorState message={error} /> : null}
        <div>
          <Button type="submit" disabled={submitting || !sourceUri.trim() || !text.trim()}>
            {submitting ? "Ingesting..." : "Ingest document"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function KnowledgeBase({ workspaceId }: { workspaceId: string }) {
  const [documents, setDocuments] = useState<KnowledgeDocumentResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    listKnowledgeDocuments(workspaceId)
      .then(setDocuments)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load knowledge documents");
      });
  }, [workspaceId, refreshToken]);

  return (
    <div className="space-y-6">
      <IngestForm workspaceId={workspaceId} onIngested={() => setRefreshToken((t) => t + 1)} />
      <Card>
        <CardHeading>Documents</CardHeading>
        <CardSubtext>Everything ingested into this workspace&apos;s retrieval corpus.</CardSubtext>
        <div className="mt-4 space-y-2">
          {error ? <ErrorState message={error} /> : null}
          {!error && documents === null ? <LoadingState label="Loading documents..." /> : null}
          {!error && documents !== null && documents.length === 0 ? (
            <EmptyState>No documents ingested yet.</EmptyState>
          ) : null}
          {documents?.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between gap-3 rounded-md border border-line bg-white px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm text-ink">{doc.source_uri}</p>
                <p className="text-xs text-ink-faint">
                  {new Date(doc.created_at).toLocaleString()}
                </p>
              </div>
              <StatusBadge status={doc.ingestion_status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
