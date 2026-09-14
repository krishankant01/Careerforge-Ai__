import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import toast from "react-hot-toast";
import { Mic, Send, Bot, User, PlayCircle, Loader2 } from "lucide-react";
import { api } from "../services/api";

type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

export default function MockInterview() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStarted, setIsStarted] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  async function startInterview() {
    setIsStarted(true);
    setIsTyping(true);
    const toastId = toast.loading("Setting up mock interview...");
    
    try {
      const convRes = await api.post("/rag/conversations", { title: "Mock Interview" });
      const newConvId = convRes.data.id;
      setConvId(newConvId);

      const response = await fetch(`/api/rag/conversations/${newConvId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("careerforge_access_token")}`,
        },
        body: JSON.stringify({
          question: "Let's start a mock interview. I am the candidate. Please ask me a technical interview question based on my resume and target job. Wait for my answer.",
          source_types: ["resume", "job", "resume_section"],
        }),
      });

      if (!response.body) throw new Error("No response body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      const aiMsgId = crypto.randomUUID();
      setMessages([{ id: aiMsgId, role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            if (dataStr === "[DONE]") continue;
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.type === "token") {
                fullText += parsed.data;
                setMessages([{ id: aiMsgId, role: "assistant", content: fullText }]);
              }
            } catch (e) {
              // ignore parse error
            }
          }
        }
      }
      toast.success("Interview started!", { id: toastId });
    } catch (err) {
      console.error(err);
      toast.error("Failed to start interview", { id: toastId });
      setIsStarted(false);
    } finally {
      setIsTyping(false);
    }
  }

  async function sendMessage(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!input.trim() || !convId || isTyping) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    try {
      const response = await fetch(`/api/rag/conversations/${convId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("careerforge_access_token")}`,
        },
        body: JSON.stringify({
          question: input,
          source_types: ["resume", "job", "resume_section"],
        }),
      });

      if (!response.body) throw new Error("No response body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      const aiMsgId = crypto.randomUUID();
      setMessages((prev) => [...prev, { id: aiMsgId, role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            if (dataStr === "[DONE]") continue;
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.type === "token") {
                fullText += parsed.data;
                setMessages((prev) => prev.map(m => m.id === aiMsgId ? { ...m, content: fullText } : m));
              }
            } catch (e) {
              // ignore parse error
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      toast.error("Failed to send message");
    } finally {
      setIsTyping(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl h-[calc(100vh-8rem)] flex flex-col space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">AI Mock Interview</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Practice your technical and behavioral skills with an AI interviewer tailored to your background.
        </p>
      </div>

      {!isStarted ? (
        <Card className="flex-1 border-dashed bg-muted/10 shadow-none flex flex-col items-center justify-center p-8 text-center animate-fade-in-up">
          <div className="p-5 bg-primary/10 text-primary rounded-full mb-5">
            <Mic className="w-10 h-10" />
          </div>
          <h3 className="text-xl font-semibold mb-3 text-foreground">Ready for your interview?</h3>
          <p className="text-muted-foreground max-w-md mx-auto mb-8 text-sm">
            The AI will ask you questions based on your resume and evaluate your answers, providing feedback just like a real technical recruiter.
          </p>
          <Button onClick={startInterview} className="gap-2">
            <PlayCircle className="w-4 h-4" />
            Start Mock Interview
          </Button>
        </Card>
      ) : (
        <Card className="flex-1 flex flex-col overflow-hidden shadow-sm animate-fade-in-up">
          <CardHeader className="border-b py-3 bg-muted/20">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
              </span>
              <CardTitle className="text-sm font-semibold text-foreground uppercase tracking-wider">Live Interview Session</CardTitle>
            </div>
          </CardHeader>
          
          <CardContent className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 custom-scrollbar bg-muted/5">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-4 max-w-[85%] animate-fade-in-up ${
                  msg.role === "user" ? "ml-auto flex-row-reverse" : ""
                }`}
              >
                <div className={`flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center ${
                  msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground border"
                }`}>
                  {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className={`p-4 rounded-lg shadow-sm text-sm ${
                  msg.role === "user" 
                    ? "bg-primary text-primary-foreground rounded-tr-sm" 
                    : "bg-background border text-foreground rounded-tl-sm"
                }`}>
                  <div className="whitespace-pre-wrap leading-relaxed">
                    {msg.content}
                  </div>
                </div>
              </div>
            ))}
            {isTyping && messages.length > 0 && messages[messages.length - 1].role === "user" && (
              <div className="flex gap-4 max-w-[85%]">
                <div className="flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center bg-secondary text-secondary-foreground border">
                  <Bot size={16} />
                </div>
                <div className="p-4 rounded-lg bg-background border text-foreground rounded-tl-sm shadow-sm flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-primary/70 rounded-full animate-bounce"></span>
                  <span className="w-1.5 h-1.5 bg-primary/70 rounded-full animate-bounce delay-75"></span>
                  <span className="w-1.5 h-1.5 bg-primary/70 rounded-full animate-bounce delay-150"></span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </CardContent>

          <div className="p-4 bg-background border-t">
            <form onSubmit={sendMessage} className="flex gap-3">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your answer..."
                disabled={isTyping}
                className="flex-1"
              />
              <Button type="submit" disabled={!input.trim() || isTyping} className="gap-2">
                {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Send
              </Button>
            </form>
          </div>
        </Card>
      )}
    </div>
  );
}
