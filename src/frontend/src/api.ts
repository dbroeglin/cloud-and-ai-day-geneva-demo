export interface Session {
  id: string;
  title: string;
  room: string;
  start: string;
  end: string;
  description: string;
  sample: boolean;
}

export interface EventInfo {
  id: string;
  name: string;
  date: string;
  timezone: string;
  venue: string;
  notice: string;
  sessions: Session[];
}

export interface Question {
  id: string;
  session_id: string;
  text: string;
  votes: number;
  created_at: string;
}

export interface QuestionPage {
  items: Question[];
  next_cursor: string | null;
}

export interface Answer {
  answer: string;
  citations: { source_id: string; title: string }[];
  refused: boolean;
  request_id: string;
}

const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const traceId = crypto.randomUUID().replaceAll("-", "");
  const spanId = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      traceparent: `00-${traceId}-${spanId}-01`,
      ...init.headers,
    },
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("The service returned an unreadable response. Please try again.");
  }
  if (!response.ok) {
    const error = body && typeof body === "object" && "error" in body ? body.error : null;
    const message = error && typeof error === "object" && "message" in error
      && typeof error.message === "string" ? error.message : "The request failed. Please try again.";
    throw new Error(message);
  }
  return body as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}
