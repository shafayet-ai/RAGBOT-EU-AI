export type Language = "en" | "bn";
export type ChatRole = "user" | "assistant";
export type UserRole = "student" | "faculty" | "admin";

export interface UserProfile {
  id: string;
  student_id: string | null;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface Citation {
  title: string;
  url: string | null;
  page: number | null;
  section: string | null;
  snippet: string;
}

export interface ChatTurn {
  role: ChatRole;
  content: string;
}

export interface ChatResponse {
  answer: string;
  sources: Citation[];
  confidence: number | null;
  grounded: boolean;
  conversation_id: string;
}

export interface HealthResponse {
  status: "ok";
  document_count: number;
}

export interface AdminOverview {
  application: string;
  application_version: string;
  python_version: string;
  rag_provider: string;
  chat_model: string;
  embedding_model: string;
  vector_store: string;
  database_engine: string;
  database_status: "connected";
  user_count: number;
  chat_count: number;
  source_document_count: number;
  indexed_chunk_count: number;
}

export interface AdminDocument {
  filename: string;
  size_bytes: number;
  modified_at: string;
  managed: boolean;
}

export interface AdminUsersResponse {
  users: UserProfile[];
  total: number;
}

async function authenticatedFetch(
  path: string,
  accessToken: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${accessToken}`);
  return fetch(`${apiBaseUrl()}${path}`, { ...init, headers, cache: "no-store" });
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
}

async function responseError(response: Response): Promise<ApiError> {
  let detail = `The assistant service returned HTTP ${response.status}.`;
  try {
    const errorBody: unknown = await response.json();
    if (
      typeof errorBody === "object" &&
      errorBody !== null &&
      "detail" in errorBody
    ) {
      if (typeof errorBody.detail === "string") {
        detail = errorBody.detail;
      } else if (Array.isArray(errorBody.detail)) {
        const validationMessages = errorBody.detail.flatMap((issue: unknown) => {
          if (
            typeof issue !== "object" ||
            issue === null ||
            !("msg" in issue) ||
            typeof issue.msg !== "string"
          ) {
            return [];
          }
          const location =
            "loc" in issue && Array.isArray(issue.loc)
              ? issue.loc.filter((part): part is string => typeof part === "string").join(".")
              : "";
          return [location ? `${location}: ${issue.msg}` : issue.msg];
        });
        if (validationMessages.length > 0) {
          detail = `Invalid request: ${validationMessages.join("; ")}`;
        }
      }
    }
  } catch {
    // Keep the HTTP status message when the server did not return JSON.
  }
  return new ApiError(detail, response.status);
}

export async function register(
  studentId: string,
  fullName: string,
  email: string,
  password: string,
): Promise<UserProfile> {
  const response = await fetch(`${apiBaseUrl()}/auth/register`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      student_id: studentId,
      full_name: fullName,
      email,
      password,
    }),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as UserProfile;
}

export async function login(
  identifier: string,
  password: string,
  loginType: "student" | "admin" = "student",
): Promise<TokenResponse> {
  const form = new URLSearchParams({
    username: identifier,
    password,
    login_type: loginType,
  });
  const response = await fetch(`${apiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form,
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as TokenResponse;
}

export async function getAdminOverview(
  accessToken: string,
): Promise<AdminOverview> {
  const response = await authenticatedFetch("/admin/overview", accessToken);
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as AdminOverview;
}

export async function getAdminUsers(
  accessToken: string,
  offset = 0,
  limit = 50,
): Promise<AdminUsersResponse> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  const response = await authenticatedFetch(
    `/admin/users?${query.toString()}`,
    accessToken,
  );
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as AdminUsersResponse;
}

export async function getAdminDocuments(
  accessToken: string,
): Promise<AdminDocument[]> {
  const response = await authenticatedFetch("/admin/documents", accessToken);
  if (!response.ok) throw await responseError(response);
  const data = (await response.json()) as { documents: AdminDocument[] };
  return data.documents;
}

export async function uploadAdminDocument(
  accessToken: string,
  file: File,
): Promise<AdminDocument> {
  const form = new FormData();
  form.append("file", file);
  const response = await authenticatedFetch("/admin/documents", accessToken, {
    method: "POST",
    body: form,
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as AdminDocument;
}

export async function deleteAdminDocument(
  accessToken: string,
  filename: string,
): Promise<void> {
  const response = await authenticatedFetch(
    `/admin/documents/${encodeURIComponent(filename)}`,
    accessToken,
    { method: "DELETE" },
  );
  if (!response.ok) throw await responseError(response);
}

export async function reindexAdminDocuments(
  accessToken: string,
): Promise<{ source_document_count: number; indexed_chunk_count: number; message: string }> {
  const response = await authenticatedFetch("/admin/reindex", accessToken, {
    method: "POST",
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as {
    source_document_count: number;
    indexed_chunk_count: number;
    message: string;
  };
}

export async function getCurrentUser(
  accessToken: string,
): Promise<UserProfile> {
  const response = await fetch(`${apiBaseUrl()}/auth/me`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as UserProfile;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl()}/health`, {
    method: "GET",
    signal,
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`The assistant service returned HTTP ${response.status}.`);
  }
  return (await response.json()) as HealthResponse;
}

export async function sendChat(
  message: string,
  language: Language,
  conversationId: string,
  accessToken: string,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch(`${apiBaseUrl()}/chat`, {
    method: "POST",
    signal,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      language,
    }),
  });

  if (!response.ok) throw await responseError(response);

  return (await response.json()) as ChatResponse;
}
