"use client";

import { CardHeading } from "@/components/ui/card";
import { EmptyState, LoadingState } from "@/components/ui/states";
import { AuditExplorer } from "@/features/audit/audit-explorer";
import { useWorkspace } from "@/features/workspace/workspace-context";

export default function AuditPage() {
  const { currentWorkspaceId, loading, workspaces } = useWorkspace();

  return (
    <div>
      <CardHeading className="mb-6 text-2xl">Audit explorer</CardHeading>
      {loading && workspaces.length === 0 ? (
        <LoadingState label="Loading workspace..." />
      ) : currentWorkspaceId ? (
        <AuditExplorer workspaceId={currentWorkspaceId} />
      ) : (
        <EmptyState>Select or create a workspace on the dashboard first.</EmptyState>
      )}
    </div>
  );
}
