// Typed client for the Interactive Lessons API.
//
// Tokens live in localStorage; requests that need auth attach the access token
// and, on a 401, transparently try the refresh token once before failing.

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const ACCESS_KEY = "il_access";
const REFRESH_KEY = "il_refresh";

export type User = {
  id: number;
  email: string;
  role: string;
  is_verified: boolean;
};

export type Project = {
  id: number;
  name: string;
  description: string | null;
  version: number;
  owner_id: number | null;
};

export type Section = {
  id: number;
  project_id: number;
  position: number;
  title: string | null;
};

export type Checkpoint = {
  id: number;
  section_id: number;
  title: string;
};

export type SnapshotSection = Section & { blocks: ContentBlock[] };

export type ProjectSnapshot = {
  project_id: number;
  project_version: number;
  sections: SnapshotSection[];
};

export type ReadingSession = {
  id: number;
  project_id: number;
  user_id: string;
  project_version: number;
  latest_version: number;
  is_stale: boolean;
  last_accessed_at: string;
  snapshot: ProjectSnapshot;
};

export type SessionResponse = {
  id: number;
  session_id: number;
  checkpoint_id: number;
  text: string | null;
  link: string | null;
  label: string | null;
};

export type BlockType = "text" | "image" | "code_block" | "checkpoint";

export type ContentBlock = {
  id: number;
  section_id: number;
  position: number;
  type: BlockType;
  text_content: string | null;
  code_content: string | null;
  image_url: string | null;
  keyword_metadata: string | null;
  checkpoint_id: number | null;
  checkpoint: Checkpoint | null;
};

export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const browser = () => typeof window !== "undefined";
const getAccess = () => (browser() ? localStorage.getItem(ACCESS_KEY) : null);
const getRefresh = () => (browser() ? localStorage.getItem(REFRESH_KEY) : null);

export function setTokens(t: Tokens) {
  localStorage.setItem(ACCESS_KEY, t.access_token);
  localStorage.setItem(REFRESH_KEY, t.refresh_token);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export const isAuthed = () => !!getAccess();

function rawFetch(path: string, init: RequestInit = {}, withAuth = false) {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (withAuth) {
    const access = getAccess();
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefresh();
  if (!refresh) return false;
  const resp = await rawFetch("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!resp.ok) {
    clearTokens();
    return false;
  }
  setTokens((await resp.json()) as Tokens);
  return true;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  withAuth = false,
): Promise<T> {
  let resp = await rawFetch(path, init, withAuth);
  if (resp.status === 401 && withAuth && getRefresh()) {
    if (await tryRefresh()) resp = await rawFetch(path, init, withAuth);
  }
  if (!resp.ok) {
    let detail: unknown = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      resp.status,
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

// --- auth ---

export function register(email: string, password: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<Tokens> {
  const body = new URLSearchParams({ username: email, password });
  const resp = await rawFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!resp.ok) throw new ApiError(resp.status, "incorrect email or password");
  const tokens = (await resp.json()) as Tokens;
  setTokens(tokens);
  return tokens;
}

export async function logout(): Promise<void> {
  const refresh = getRefresh();
  if (refresh) {
    try {
      await rawFetch("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
    } catch {
      /* best effort */
    }
  }
  clearTokens();
}

export const me = () => request<User>("/auth/me", {}, true);

// --- projects ---

export const listProjects = () => request<Project[]>("/projects");
export const getProject = (id: number) => request<Project>(`/projects/${id}`);
export const createProject = (name: string, description?: string) =>
  request<Project>(
    "/projects",
    { method: "POST", body: JSON.stringify({ name, description }) },
    true,
  );

// --- sections + blocks ---

export const listSections = (projectId: number) =>
  request<Section[]>(`/projects/${projectId}/sections`);

export const listBlocks = (projectId: number, sectionId: number) =>
  request<ContentBlock[]>(
    `/projects/${projectId}/sections/${sectionId}/blocks`,
  );

// --- reading sessions + responses (auth required) ---

export const startSession = (projectId: number) =>
  request<ReadingSession>(
    `/projects/${projectId}/sessions`,
    { method: "POST" },
    true,
  );

export const refreshSession = (projectId: number, sessionId: number) =>
  request<ReadingSession>(
    `/projects/${projectId}/sessions/${sessionId}/refresh`,
    { method: "POST" },
    true,
  );

export const listResponses = (
  projectId: number,
  sessionId: number,
  checkpointId: number,
) =>
  request<SessionResponse[]>(
    `/projects/${projectId}/sessions/${sessionId}/checkpoints/${checkpointId}/responses`,
    {},
    true,
  );

export const addResponse = (
  projectId: number,
  sessionId: number,
  checkpointId: number,
  body: { text?: string; link?: string; label?: string },
) =>
  request<SessionResponse>(
    `/projects/${projectId}/sessions/${sessionId}/checkpoints/${checkpointId}/responses`,
    { method: "POST", body: JSON.stringify(body) },
    true,
  );
