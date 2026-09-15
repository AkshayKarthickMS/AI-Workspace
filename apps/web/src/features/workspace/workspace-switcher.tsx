"use client";

import { useIdentity } from "@/features/identity/identity-context";
import { useWorkspace } from "@/features/workspace/workspace-context";

export function WorkspaceSwitcher() {
  const { identitySubject, ready } = useIdentity();
  const { workspaces, currentWorkspaceId, selectWorkspace, loading } = useWorkspace();

  if (!ready || !identitySubject) return null;
  if (!loading && workspaces.length === 0) return null;

  return (
    <select
      value={currentWorkspaceId ?? ""}
      onChange={(event) => selectWorkspace(event.target.value)}
      className="w-full rounded-md border border-line bg-white px-3 py-1.5 text-xs text-ink focus:border-ink-muted focus:outline-none"
    >
      {workspaces.map((workspace) => (
        <option key={workspace.id} value={workspace.id}>
          {workspace.name}
        </option>
      ))}
    </select>
  );
}
