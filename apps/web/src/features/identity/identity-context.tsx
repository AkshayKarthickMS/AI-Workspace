"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import {
  clearStoredIdentity,
  getStoredDisplayName,
  getStoredIdentity,
  setStoredIdentity,
} from "@/lib/identity";

interface IdentityContextValue {
  identitySubject: string | null;
  displayName: string | null;
  ready: boolean;
  setIdentity: (identitySubject: string, displayName?: string) => void;
  clearIdentity: () => void;
}

const IdentityContext = createContext<IdentityContextValue | undefined>(undefined);

export function IdentityProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [identitySubject, setIdentitySubject] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // Read localStorage only after mount -- reading it during render would
  // differ between the server-rendered markup (no localStorage) and the
  // client's first render, causing a hydration mismatch.
  useEffect(() => {
    setIdentitySubject(getStoredIdentity());
    setDisplayName(getStoredDisplayName());
    setReady(true);
  }, []);

  const setIdentity = (subject: string, name?: string): void => {
    setStoredIdentity(subject, name);
    setIdentitySubject(subject);
    setDisplayName(getStoredDisplayName());
  };

  const clearIdentity = (): void => {
    clearStoredIdentity();
    setIdentitySubject(null);
    setDisplayName(null);
  };

  return (
    <IdentityContext.Provider
      value={{ identitySubject, displayName, ready, setIdentity, clearIdentity }}
    >
      {children}
    </IdentityContext.Provider>
  );
}

export function useIdentity(): IdentityContextValue {
  const context = useContext(IdentityContext);
  if (!context) throw new Error("useIdentity must be used within an IdentityProvider");
  return context;
}
