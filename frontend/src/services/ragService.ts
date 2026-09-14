/**
 * RAG API client — Phase 5.
 *
 * Talks to the /api/rag/* endpoints.
 * All calls are authenticated via the JWT interceptor in api.ts.
 */
import { api, extractErrorMessage } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Citation {
  document_id: string;
  source_type: "resume" | "resume_section" | "job";
  source_id: string;
  title: string;
  excerpt: string;
  score: number;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export interface ConversationList {
  conversations: Conversation[];
  total: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface ChatAnswer {
  conversation_id: string;
  answer: string;
  citations: Citation[];
}

export interface ReindexStatus {
  chunks_indexed: number;
  source_breakdown: Record<string, number>;
  message: string;
}

export type SourceType = "resume" | "resume_section" | "job";

// SSE stream event
export interface StreamEvent {
  type: "citations" | "token" | "done" | "error";
  data: string | Citation[] | "";
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

export async function createConversation(title = "Career chat"): Promise<Conversation> {
  const res = await api.post<Conversation>("/rag/conversations", { title });
  return res.data;
}

export async function listConversations(): Promise<ConversationList> {
  const res = await api.get<ConversationList>("/rag/conversations");
  return res.data;
}

export async function deleteConversation(id: string): Promise<void> {
  await api.delete(`/rag/conversations/${id}`);
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

export async function getHistory(conversationId: string): Promise<Message[]> {
  const res = await api.get<Message[]>(`/rag/conversations/${conversationId}/messages`);
  return res.data;
}

export async function sendMessage(
  conversationId: string,
  question: string,
  sourceTypes?: SourceType[]
): Promise<ChatAnswer> {
  const res = await api.post<ChatAnswer>(
    `/rag/conversations/${conversationId}/messages`,
    { question, source_types: sourceTypes ?? null }
  );
  return res.data;
}

/**
 * Stream a chat response via Server-Sent Events.
 *
 * Returns an object with:
 *  - `stream`: ReadableStreamDefaultReader that yields StreamEvent objects
 *  - `abort`: function to cancel the request
 *
 * Usage:
 *   const { reader, abort } = streamMessage(convId, question);
 *   for await (const event of readStream(reader)) { ... }
 */
export function streamMessage(
  conversationId: string,
  question: string,
  sourceTypes?: SourceType[]
): { abort: () => void; promise: Promise<{ citations: Citation[]; answer: string }> } {
  const controller = new AbortController();

  // Build auth header
  const token = localStorage.getItem("careerforge_access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const promise = (async () => {
    const response = await fetch(
      `/api/rag/conversations/${conversationId}/messages/stream`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ question, source_types: sourceTypes ?? null }),
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status}`);
    }

    // This is a resolved promise that external code can read from.
    // Real streaming is handled via the onToken/onCitations callbacks below.
    return { citations: [] as Citation[], answer: "" };
  })();

  return { abort: () => controller.abort(), promise };
}

/**
 * Higher-level streaming helper with callbacks.
 *
 * @param conversationId  Target conversation
 * @param question        User's question
 * @param sourceTypes     Optional source filter
 * @param onCitations     Called once with the citations array
 * @param onToken         Called for each streamed token
 * @param onDone          Called when streaming is complete
 * @param onError         Called on error
 * @returns abort function
 */
export function streamChat(
  conversationId: string,
  question: string,
  sourceTypes: SourceType[] | undefined,
  onCitations: (citations: Citation[]) => void,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): () => void {
  const controller = new AbortController();

  const token = localStorage.getItem("careerforge_access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  (async () => {
    try {
      const response = await fetch(
        `/api/rag/conversations/${conversationId}/messages/stream`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ question, source_types: sourceTypes ?? null }),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        onError(`Request failed: ${response.status}`);
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event: StreamEvent = JSON.parse(line.slice(6));
            if (event.type === "citations") {
              onCitations(event.data as Citation[]);
            } else if (event.type === "token") {
              onToken(event.data as string);
            } else if (event.type === "done") {
              onDone();
            } else if (event.type === "error") {
              onError(event.data as string);
            }
          } catch {
            // Ignore malformed lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError(extractErrorMessage(err));
      }
    }
  })();

  return () => controller.abort();
}

// ---------------------------------------------------------------------------
// Reindex
// ---------------------------------------------------------------------------

export async function reindex(): Promise<ReindexStatus> {
  const res = await api.post<ReindexStatus>("/rag/reindex");
  return res.data;
}
