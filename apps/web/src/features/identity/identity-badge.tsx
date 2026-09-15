"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { useIdentity } from "@/features/identity/identity-context";

export function IdentityBadge() {
  const { identitySubject, displayName, ready, setIdentity } = useIdentity();
  const [editing, setEditing] = useState(false);
  const [subjectDraft, setSubjectDraft] = useState("");
  const [nameDraft, setNameDraft] = useState("");

  if (!ready) return null;

  if (editing) {
    return (
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!subjectDraft.trim()) return;
          setIdentity(subjectDraft.trim(), nameDraft.trim());
          setEditing(false);
        }}
      >
        <Input
          autoFocus
          placeholder="you@example.com"
          value={subjectDraft}
          onChange={(event) => setSubjectDraft(event.target.value)}
          className="w-44"
        />
        <Input
          placeholder="Display name (optional)"
          value={nameDraft}
          onChange={(event) => setNameDraft(event.target.value)}
          className="w-40"
        />
        <Button type="submit" variant="primary" className="px-3 py-1.5 text-xs">
          Save
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="px-3 py-1.5 text-xs"
          onClick={() => setEditing(false)}
        >
          Cancel
        </Button>
      </form>
    );
  }

  return (
    <button
      type="button"
      onClick={() => {
        setSubjectDraft(identitySubject ?? "");
        setNameDraft(displayName ?? "");
        setEditing(true);
      }}
      className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-200 hover:border-cyan-400/50"
      title="Local development identity -- not real authentication"
    >
      {identitySubject ? (displayName ?? identitySubject) : "Set identity"}
    </button>
  );
}
