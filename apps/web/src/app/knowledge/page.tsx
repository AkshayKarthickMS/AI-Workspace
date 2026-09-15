"use client";

import { CardHeading } from "@/components/ui/card";
import { EmptyState, LoadingState } from "@/components/ui/states";
import { KnowledgeBase } from "@/features/knowledge/knowledge-base";
import { useWorkspace } from "@/features/workspace/workspace-context";

export default function KnowledgePage() {
  const { currentWorkspaceId, loading, workspaces } = useWorkspace();

  return (
    <div>
      <CardHeading className="mb-6 text-2xl">Knowledge base</CardHeading>
      {loading && workspaces.length === 0 ? (
        <LoadingState label="Loading workspace..." />
      ) : currentWorkspaceId ? (
        <KnowledgeBase workspaceId={currentWorkspaceId} />
      ) : (
        <EmptyState>Select or create a workspace on the dashboard first.</EmptyState>
      )}
    </div>
  );
}
