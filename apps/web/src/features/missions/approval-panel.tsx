"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { Label, Textarea } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { resolveApproval } from "@/lib/api-client";

interface Props {
  workspaceId: string;
  runId: string;
  status: string;
  approval: Record<string, unknown> | null | undefined;
  escalation: Record<string, unknown> | null | undefined;
  onResolved: () => void;
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function ApprovalPanel({
  workspaceId,
  runId,
  status,
  approval,
  escalation,
  onResolved,
}: Props) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isEscalation = status === "awaiting_escalation";
  const isApproval = status === "awaiting_approval";
  if (!isEscalation && !isApproval) return null;

  const record = isEscalation ? escalation : approval;
  const gateReason = record ? asString(record.reason) : null;
  const violations = Array.isArray(record?.violations)
    ? (record.violations as unknown[]).filter((v): v is string => typeof v === "string")
    : [];

  const decide = async (decision: "approve" | "reject") => {
    setSubmitting(decision);
    setError(null);
    try {
      await resolveApproval(workspaceId, runId, {
        decision,
        reason: reason.trim() || undefined,
      });
      setReason("");
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record decision");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <Card className="border-amber-300">
      <div className="flex items-center gap-3">
        <CardHeading>{isEscalation ? "Compliance escalation" : "Plan approval required"}</CardHeading>
        <Badge tone="warning">action needed</Badge>
      </div>
      <CardSubtext>
        {isEscalation
          ? "Compliance flagged this run mid-execution. Review the violations before deciding whether to continue."
          : "Review the drafted plan above and approve it to begin execution, or reject it to stop the run."}
      </CardSubtext>
      {gateReason ? <p className="mt-3 text-sm text-ink">{gateReason}</p> : null}
      {violations.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-red-700">
          {violations.map((violation, index) => (
            <li key={index}>{violation}</li>
          ))}
        </ul>
      ) : null}
      <div className="mt-4">
        <Label htmlFor="decision-reason">Reason (optional)</Label>
        <Textarea
          id="decision-reason"
          rows={2}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Add context for the audit trail"
        />
      </div>
      {error ? (
        <div className="mt-3">
          <ErrorState message={error} />
        </div>
      ) : null}
      <div className="mt-4 flex gap-3">
        <Button
          variant="primary"
          disabled={submitting !== null}
          onClick={() => void decide("approve")}
        >
          {submitting === "approve" ? "Approving..." : "Approve"}
        </Button>
        <Button
          variant="danger"
          disabled={submitting !== null}
          onClick={() => void decide("reject")}
        >
          {submitting === "reject" ? "Rejecting..." : "Reject"}
        </Button>
      </div>
    </Card>
  );
}
