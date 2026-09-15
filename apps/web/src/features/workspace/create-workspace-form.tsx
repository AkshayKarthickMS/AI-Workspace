"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { Input, Label } from "@/components/ui/field";
import { useWorkspace } from "@/features/workspace/workspace-context";
import { createWorkspace } from "@/lib/api-client";

export function CreateWorkspaceForm() {
  const { refresh, selectWorkspace } = useWorkspace();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <Card>
      <CardHeading>Create your first workspace</CardHeading>
      <CardSubtext>
        Workspaces scope missions, knowledge, and audit history. You need at least one to get
        started.
      </CardSubtext>
      <form
        className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!name.trim() || submitting) return;
          setSubmitting(true);
          setError(null);
          try {
            const workspace = await createWorkspace({ name: name.trim() });
            refresh();
            selectWorkspace(workspace.id);
            setName("");
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create workspace");
          } finally {
            setSubmitting(false);
          }
        }}
      >
        <div className="flex-1">
          <Label htmlFor="workspace-name">Workspace name</Label>
          <Input
            id="workspace-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Acme Corp"
            required
          />
        </div>
        <Button type="submit" disabled={submitting || !name.trim()}>
          {submitting ? "Creating..." : "Create workspace"}
        </Button>
      </form>
      {error ? (
        <div className="mt-4">
          <ErrorState message={error} />
        </div>
      ) : null}
    </Card>
  );
}
