"use client";

import type { WorkspaceResponse } from "@aegisos/shared";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useIdentity } from "@/features/identity/identity-context";
import { listWorkspaces } from "@/lib/api-client";

const CURRENT_WORKSPACE_KEY = "aegisos.currentWorkspaceId";

interface WorkspaceContextValue {
  workspaces: WorkspaceResponse[];
  currentWorkspaceId: string | null;
  currentWorkspace: WorkspaceResponse | null;
  loading: boolean;
  error: string | null;
  selectWorkspace: (workspaceId: string) => void;
  refresh: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const { identitySubject, ready } = useIdentity();
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    if (!ready || !identitySubject) {
      setWorkspaces([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    listWorkspaces()
      .then((rows) => {
        if (cancelled) return;
        setWorkspaces(rows);
        setCurrentWorkspaceId((previous) => {
          if (previous && rows.some((row) => row.id === previous)) return previous;
          const stored =
            typeof window !== "undefined"
              ? window.localStorage.getItem(CURRENT_WORKSPACE_KEY)
              : null;
          if (stored && rows.some((row) => row.id === stored)) return stored;
          return rows[0]?.id ?? null;
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load workspaces");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ready, identitySubject, refreshToken]);

  const selectWorkspace = useCallback((workspaceId: string) => {
    setCurrentWorkspaceId(workspaceId);
    try {
      window.localStorage.setItem(CURRENT_WORKSPACE_KEY, workspaceId);
    } catch {
      // localStorage may be unavailable -- selection just won't persist.
    }
  }, []);

  const refresh = useCallback(() => setRefreshToken((token) => token + 1), []);

  const currentWorkspace = useMemo(
    () => workspaces.find((row) => row.id === currentWorkspaceId) ?? null,
    [workspaces, currentWorkspaceId],
  );

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        currentWorkspaceId,
        currentWorkspace,
        loading,
        error,
        selectWorkspace,
        refresh,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("useWorkspace must be used within a WorkspaceProvider");
  return context;
}
