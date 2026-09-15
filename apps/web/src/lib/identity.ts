// Local development identity mode only (ARCHITECTURE.md §9/§12) -- the API
// treats whatever is sent here as an already-authenticated caller, so this
// is deliberately not "login" UI, just the header every request needs.
// Never mistake this for real authentication.

const IDENTITY_KEY = "aegisos.identitySubject";
const DISPLAY_NAME_KEY = "aegisos.displayName";

function readStorage(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // localStorage may be unavailable (private browsing, storage full, etc.)
    // -- the identity just won't persist across reloads.
  }
}

function removeStorage(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export function getStoredIdentity(): string | null {
  return readStorage(IDENTITY_KEY);
}

export function getStoredDisplayName(): string | null {
  return readStorage(DISPLAY_NAME_KEY);
}

export function setStoredIdentity(identitySubject: string, displayName?: string): void {
  writeStorage(IDENTITY_KEY, identitySubject);
  writeStorage(DISPLAY_NAME_KEY, displayName && displayName.trim() ? displayName : identitySubject);
}

export function clearStoredIdentity(): void {
  removeStorage(IDENTITY_KEY);
  removeStorage(DISPLAY_NAME_KEY);
}
