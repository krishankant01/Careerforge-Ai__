import { useCallback, useEffect, useRef, useState } from "react";
import {
  Citation,
  Conversation,
  Message,
  SourceType,
  createConversation,
  deleteConversation,
  getHistory,
  listConversations,
  reindex,
  streamChat,
} from "../services/ragService";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import toast from "react-hot-toast";
import { MessageSquare, Bot, User, Send, RefreshCw, Trash2, Plus, Sparkles } from "lucide-react";

function sourceLabel(type: string) {
  const map: Record<string, string> = {
    resume: "📄 Resume",
    resume_section: "📑 Section",
    job: "💼 Job",
  };
  return map[type] ?? type;
}

function renderMarkdown(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong class='text-foreground font-semibold'>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em class='text-muted-foreground'>$1</em>")
    .replace(/`(.+?)`/g, '<code class="bg-muted px-1.5 py-0.5 rounded text-sm text-foreground border font-mono">$1</code>')
    .replace(/\[Source (\d+)\]/g, '<span class="bg-secondary text-secondary-foreground border px-1.5 py-0.5 rounded text-[10px] font-bold ml-1.5 inline-flex items-center justify-center">[Source $1]</span>')
    .replace(/\n\n/g, "</p><p class='mt-2'>")
    .replace(/\n/g, "<br/>");
}

function CitationsPanel({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(false);
  if (!citations.length) return null;
  return (
    <div className="mt-3 border rounded-md bg-muted/30 overflow-hidden text-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full px-4 py-2.5 text-xs font-semibold tracking-wide text-muted-foreground hover:bg-muted/50 transition-colors uppercase"
      >
        <span className="flex items-center gap-2">
          📚 {citations.length} source{citations.length !== 1 ? "s" : ""} cited
        </span>
        <span className="text-muted-foreground">{open ? "▼" : "▲"}</span>
      </button>
      {open && (
        <div className="p-3 grid grid-cols-1 gap-2.5 border-t bg-muted/10">
          {citations.map((c, i) => (
            <div key={c.document_id + i} className="bg-background p-3 rounded-md border shadow-sm text-left hover:bg-muted/10 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <span className="bg-secondary text-secondary-foreground border px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase">
                  Source {i + 1}
                </span>
                <span className="text-[11px] text-muted-foreground font-medium tracking-wide">{sourceLabel(c.source_type)}</span>
                <span className="ml-auto text-[10px] font-bold text-green-700 bg-green-100 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800 px-2 py-0.5 rounded border uppercase tracking-wider">
                  {Math.round(c.score * 100)}% Match
                </span>
              </div>
              <div className="text-sm font-semibold text-foreground mb-1.5">{c.title}</div>
              <div className="text-xs text-muted-foreground leading-relaxed line-clamp-3 italic">
                "{c.excerpt}"
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CareerChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<(Message & { isStreaming?: boolean })[]>([]);
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [input, setInput] = useState("");
  const [sourceFilter] = useState<Set<SourceType>>(new Set(["resume", "resume_section", "job"]));
  const [isStreaming, setIsStreaming] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);

  const abortRef = useRef<() => void>();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const loadConversations = async () => {
    try {
      const data = await listConversations();
      setConversations(data.conversations);
      if (data.conversations.length && !activeConvId) {
        await selectConversation(data.conversations[0].id);
      }
    } catch {
      toast.error("Failed to load conversations");
    }
  };

  const selectConversation = async (id: string) => {
    setActiveConvId(id);
    setStreamingCitations([]);
    try {
      const history = await getHistory(id);
      setMessages(history);
    } catch {
      setMessages([]);
    }
  };

  const handleNewChat = async () => {
    try {
      const conv = await createConversation("New Conversation");
      setConversations((prev) => [conv, ...prev]);
      setActiveConvId(conv.id);
      setMessages([]);
      setStreamingCitations([]);
    } catch (err) {
      toast.error("Failed to create conversation");
    }
  };

  const handleDeleteConv = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConvId === id) {
        const remaining = conversations.filter((c) => c.id !== id);
        if (remaining.length) {
          await selectConversation(remaining[0].id);
        } else {
          setActiveConvId(null);
          setMessages([]);
        }
      }
    } catch {
      toast.error("Failed to delete conversation");
    }
  };

  const handleReindex = async () => {
    setIsReindexing(true);
    const toastId = toast.loading("Reindexing your knowledge base...");
    try {
      const result = await reindex();
      toast.success(`Indexed ${result.chunks_indexed} chunks successfully`, { id: toastId });
    } catch {
      toast.error("Reindex failed", { id: toastId });
    } finally {
      setIsReindexing(false);
    }
  };

  const handleSend = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;
    
    if (!activeConvId) {
      await handleNewChat();
      toast("Created new chat. Please send your message again.", { icon: 'ℹ️' });
      return;
    }

    const question = input.trim();
    setInput("");
    setStreamingCitations([]);

    const tempUserMsg: Message & { isStreaming?: boolean } = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      citations: [],
      created_at: new Date().toISOString(),
    };
    const tempAiMsg: Message & { isStreaming?: boolean } = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      citations: [],
      created_at: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, tempUserMsg, tempAiMsg]);
    setIsStreaming(true);

    const types = Array.from(sourceFilter) as SourceType[];

    const abort = streamChat(
      activeConvId,
      question,
      types,
      (citations) => {
        setStreamingCitations(citations);
        setMessages((prev) => prev.map((m) => m.id === tempAiMsg.id ? { ...m, citations } : m));
      },
      (token) => {
        setMessages((prev) => prev.map((m) => m.id === tempAiMsg.id ? { ...m, content: m.content + token } : m));
      },
      () => {
        setIsStreaming(false);
        setMessages((prev) => prev.map((m) => m.id === tempAiMsg.id ? { ...m, isStreaming: false } : m));
        abortRef.current = undefined;
      },
      (errMsg) => {
        setIsStreaming(false);
        toast.error(errMsg);
        setMessages((prev) => prev.filter((m) => m.id !== tempAiMsg.id));
        abortRef.current = undefined;
      }
    );

    abortRef.current = abort;
  }, [input, isStreaming, activeConvId, sourceFilter]);

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Career Intelligence Chat</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Ask questions about your resume, matched jobs, and skills.
          </p>
        </div>
        <Button onClick={handleReindex} disabled={isReindexing} variant="outline" size="sm">
          <RefreshCw className={`w-4 h-4 mr-2 ${isReindexing ? "animate-spin" : ""}`} />
          Reindex KB
        </Button>
      </div>

      <div className="flex flex-1 overflow-hidden gap-4 pb-6">
        {/* Sidebar */}
        <Card className="w-64 flex-shrink-0 flex-col hidden md:flex h-full shadow-sm">
          <div className="p-4 border-b">
            <Button onClick={handleNewChat} className="w-full justify-start">
              <Plus className="w-4 h-4 mr-2" />
              New Chat
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
            {conversations.length === 0 ? (
              <div className="text-center p-6 text-xs text-muted-foreground italic">No conversations yet</div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  className={`group flex items-center justify-between px-3 py-2.5 rounded-md cursor-pointer transition-colors ${
                    activeConvId === conv.id ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <MessageSquare className={`w-4 h-4 flex-shrink-0 ${activeConvId === conv.id ? "text-primary" : "text-muted-foreground"}`} />
                    <span className="text-xs truncate">{conv.title}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConv(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors rounded"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Chat Area */}
        <Card className="flex-1 flex flex-col h-full shadow-sm overflow-hidden">
          {!activeConvId ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-muted/10">
              <div className="p-5 bg-primary/10 rounded-full mb-5">
                <Sparkles className="w-10 h-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">Welcome to Career AI</h3>
              <p className="max-w-md text-muted-foreground mb-6 text-sm">Select a conversation or start a new one to ask about your career, resume, and job matches.</p>
              <Button onClick={handleNewChat}>Start New Chat</Button>
            </div>
          ) : (
            <>
              <CardContent className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 custom-scrollbar bg-muted/5">
                {messages.length === 0 && !isStreaming && (
                  <div className="text-center py-16 text-muted-foreground">
                    <p className="text-sm font-medium">Ask your first question!</p>
                    <p className="text-xs mt-1 opacity-70">(Make sure to Reindex if you just uploaded a resume).</p>
                  </div>
                )}
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex gap-4 max-w-[85%] animate-fade-in-up ${msg.role === "user" ? "ml-auto flex-row-reverse" : ""}`}>
                    <div className={`flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center ${msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground border"}`}>
                      {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
                    </div>
                    <div className="flex flex-col gap-1.5 max-w-full">
                      <div className={`p-4 rounded-lg text-sm ${msg.role === "user" ? "bg-primary text-primary-foreground rounded-tr-sm" : "bg-background border shadow-sm text-foreground rounded-tl-sm"}`}>
                        <div 
                          className={`whitespace-pre-wrap leading-relaxed ${msg.role === "assistant" ? "prose prose-sm dark:prose-invert max-w-none prose-p:my-0 prose-p:mb-2 last:prose-p:mb-0" : ""}`}
                          dangerouslySetInnerHTML={msg.role === "assistant" ? { __html: renderMarkdown(msg.content) } : undefined}
                        >
                          {msg.role === "user" ? msg.content : undefined}
                        </div>
                        {msg.isStreaming && (
                          <span className="inline-flex gap-1 items-center ml-1 mt-1">
                            <span className="w-1.5 h-1.5 bg-primary/70 rounded-full animate-bounce"></span>
                            <span className="w-1.5 h-1.5 bg-primary/70 rounded-full animate-bounce delay-75"></span>
                            <span className="w-1.5 h-1.5 bg-primary/70 rounded-full animate-bounce delay-150"></span>
                          </span>
                        )}
                      </div>
                      
                      {msg.role === "assistant" && !msg.isStreaming && msg.citations && msg.citations.length > 0 && (
                        <CitationsPanel citations={msg.citations} />
                      )}
                      {msg.role === "assistant" && msg.isStreaming && streamingCitations.length > 0 && (
                        <CitationsPanel citations={streamingCitations} />
                      )}
                    </div>
                  </div>
                ))}
                <div ref={bottomRef} />
              </CardContent>

              <div className="p-4 bg-background border-t">
                <form onSubmit={handleSend} className="flex gap-3">
                  <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask about your resume or skills..."
                    disabled={isStreaming}
                    className="flex-1"
                  />
                  <Button type="submit" disabled={!input.trim() || isStreaming}>
                    <Send className="w-4 h-4 mr-2" />
                    Send
                  </Button>
                </form>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
