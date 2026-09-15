"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeading, CardSubtext } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { LoadingState } from "@/components/ui/states";
import { HealthStatus } from "@/features/dashboard/health-status";
import { useIdentity } from "@/features/identity/identity-context";
import { MissionList } from "@/features/missions/mission-list";
import { CreateWorkspaceForm } from "@/features/workspace/create-workspace-form";
import { useWorkspace } from "@/features/workspace/workspace-context";

function GetStarted() {
  const { setIdentity } = useIdentity();
  const [subject, setSubject] = useState("");
  const [name, setName] = useState("");

  return (
    <Card>
      <CardHeading>Set your identity</CardHeading>
      <CardSubtext>
        AegisOS runs in local development identity mode: every request is attributed to whatever
        subject you set here. This is not a login -- it is the header the API expects.
      </CardSubtext>
      <form
        className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (!subject.trim()) return;
          setIdentity(subject.trim(), name.trim());
        }}
      >
        <div className="flex-1">
          <Label htmlFor="identity-subject">Identity subject</Label>
          <Input
            id="identity-subject"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="you@example.com"
            required
          />
        </div>
        <div className="flex-1">
          <Label htmlFor="identity-name">Display name (optional)</Label>
          <Input
            id="identity-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Your name"
          />
        </div>
        <Button type="submit" disabled={!subject.trim()}>
          Continue
        </Button>
      </form>
    </Card>
  );
}

export default function DashboardPage() {
  const { identitySubject, ready } = useIdentity();
  const { currentWorkspaceId, workspaces, loading } = useWorkspace();

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Dashboard</h1>

      <section className="mt-6">
        <Card>
          <CardHeading>Platform connection</CardHeading>
          <CardSubtext>Live status is read from the FastAPI health endpoint.</CardSubtext>
          <div className="mt-5">
            <HealthStatus />
          </div>
        </Card>
      </section>

      <section className="mt-6">
        {!ready ? (
          <LoadingState />
        ) : !identitySubject ? (
          <GetStarted />
        ) : loading && workspaces.length === 0 ? (
          <LoadingState label="Loading workspaces..." />
        ) : workspaces.length === 0 ? (
          <CreateWorkspaceForm />
        ) : currentWorkspaceId ? (
          <MissionList workspaceId={currentWorkspaceId} />
        ) : (
          <LoadingState />
        )}
      </section>
    </div>
  );
}
