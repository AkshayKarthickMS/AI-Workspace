"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { useWorkspace } from "@/features/workspace/workspace-context";
import { createMission } from "@/lib/api-client";

function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export default function NewMissionPage() {
  const router = useRouter();
  const { currentWorkspaceId } = useWorkspace();
  const [rawRequest, setRawRequest] = useState("");
  const [objective, setObjective] = useState("");
  const [constraints, setConstraints] = useState("");
  const [successCriteria, setSuccessCriteria] = useState("");
  const [datasetPath, setDatasetPath] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!currentWorkspaceId) {
    return <ErrorState message="Select a workspace before creating a mission." />;
  }

  return (
    <Card>
      <CardHeading>New mission</CardHeading>
      <CardSubtext>
        Describe what you need done. AegisOS plans the work and stops for your approval before
        anything executes.
      </CardSubtext>
      <form
        className="mt-6 flex flex-col gap-5"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!rawRequest.trim() || !objective.trim() || submitting) return;
          setSubmitting(true);
          setError(null);
          try {
            const mission = await createMission(currentWorkspaceId, {
              raw_request: rawRequest.trim(),
              objective: objective.trim(),
              constraints: linesToList(constraints),
              success_criteria: linesToList(successCriteria),
              context: datasetPath.trim() ? { dataset_path: datasetPath.trim() } : {},
            });
            router.push(`/missions/${mission.id}`);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create mission");
            setSubmitting(false);
          }
        }}
      >
        <div>
          <Label htmlFor="raw-request">Request</Label>
          <Textarea
            id="raw-request"
            rows={3}
            value={rawRequest}
            onChange={(event) => setRawRequest(event.target.value)}
            placeholder="What are you asking AegisOS to do?"
            required
          />
        </div>
        <div>
          <Label htmlFor="objective">Objective</Label>
          <Textarea
            id="objective"
            rows={3}
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="What does success look like, stated as a clear objective?"
            required
          />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <Label htmlFor="constraints">Constraints (one per line)</Label>
            <Textarea
              id="constraints"
              rows={4}
              value={constraints}
              onChange={(event) => setConstraints(event.target.value)}
              placeholder="e.g. Use only the provided dataset"
            />
          </div>
          <div>
            <Label htmlFor="success-criteria">Success criteria (one per line)</Label>
            <Textarea
              id="success-criteria"
              rows={4}
              value={successCriteria}
              onChange={(event) => setSuccessCriteria(event.target.value)}
              placeholder="e.g. Report includes revenue by region"
            />
          </div>
        </div>
        <div>
          <Label htmlFor="dataset-path">Dataset path (optional)</Label>
          <Input
            id="dataset-path"
            value={datasetPath}
            onChange={(event) => setDatasetPath(event.target.value)}
            placeholder="data/demo/sales_data.csv"
          />
        </div>
        {error ? <ErrorState message={error} /> : null}
        <div className="flex gap-3">
          <Button type="submit" disabled={submitting || !rawRequest.trim() || !objective.trim()}>
            {submitting ? "Creating..." : "Create mission"}
          </Button>
          <Button type="button" variant="secondary" onClick={() => router.push("/")}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
