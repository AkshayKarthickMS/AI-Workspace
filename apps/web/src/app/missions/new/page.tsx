"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { useWorkspace } from "@/features/workspace/workspace-context";
import { createMission, uploadDataset } from "@/lib/api-client";

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
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
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
          <Label htmlFor="dataset-upload">Dataset (optional)</Label>
          <Input
            id="dataset-upload"
            type="file"
            accept=".csv,.xlsx"
            disabled={uploading}
            className="file:mr-3 file:rounded-md file:border-0 file:bg-cyan-500 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-950"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (!file) return;
              setUploading(true);
              setUploadError(null);
              try {
                const result = await uploadDataset(currentWorkspaceId, file);
                setDatasetPath(result.dataset_path);
                setUploadedFileName(`${file.name} (${result.rows.toLocaleString()} rows)`);
              } catch (err) {
                setUploadError(err instanceof Error ? err.message : "Failed to upload dataset");
              } finally {
                setUploading(false);
              }
            }}
          />
          <p className="mt-1.5 text-xs text-slate-500">
            {uploading
              ? "Uploading..."
              : uploadedFileName
                ? `Using uploaded file: ${uploadedFileName}`
                : "Upload your own CSV or Excel file, or enter a server-side path below."}
          </p>
          {uploadError ? <ErrorState message={uploadError} /> : null}
          <Input
            id="dataset-path"
            className="mt-2"
            value={datasetPath}
            onChange={(event) => {
              setDatasetPath(event.target.value);
              setUploadedFileName(null);
            }}
            placeholder="data/demo/sales_data.csv"
          />
        </div>
        {error ? <ErrorState message={error} /> : null}
        <div className="flex gap-3">
          <Button
            type="submit"
            disabled={submitting || uploading || !rawRequest.trim() || !objective.trim()}
          >
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
