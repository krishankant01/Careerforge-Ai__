import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import toast from "react-hot-toast";
import { Code, Sparkles, Loader2 } from "lucide-react";
import { api } from "../services/api";

function renderMarkdown(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong class='text-foreground font-semibold'>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em class='text-muted-foreground'>$1</em>")
    .replace(/`(.+?)`/g, '<code class="bg-muted px-1.5 py-0.5 rounded text-sm text-foreground border font-mono">$1</code>')
    .replace(/### (.+)/g, '<h3 class="text-base font-bold mt-5 mb-2 text-foreground flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-primary/80"></span>$1</h3>')
    .replace(/## (.+)/g, '<h2 class="text-lg font-bold mt-6 mb-3 border-b pb-1.5 text-foreground">$1</h2>')
    .replace(/# (.+)/g, '<h1 class="text-xl font-bold mt-6 mb-4 text-foreground tracking-tight">$1</h1>')
    .replace(/- (.+)/g, '<li class="ml-4 mb-1.5 flex items-start text-muted-foreground"><span class="text-primary/60 mr-2 mt-1 text-[10px]">●</span><span>$1</span></li>')
    .replace(/\n\n/g, "</p><p class='mt-3 text-muted-foreground leading-relaxed text-sm'>")
    .replace(/\n/g, "<br/>");
}

export default function ProjectGenerator() {
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function generateProjects() {
    setIsGenerating(true);
    setResult(null);
    const toastId = toast.loading("Analyzing profile and generating projects...");
    
    try {
      // Create a temporary conversation for the generation
      const convRes = await api.post("/rag/conversations", { title: "Project Generation" });
      const convId = convRes.data.id;

      // Stream chat
      const response = await fetch(`/api/rag/conversations/${convId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("careerforge_access_token")}`,
        },
        body: JSON.stringify({
          question: "Please generate personalized portfolio projects based on my resume, target jobs, and skill gaps. Use the Project Recommendation Agent.",
          source_types: ["resume", "job", "resume_section"],
        }),
      });

      if (!response.body) throw new Error("No response body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

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
                setResult(fullText);
              }
            } catch (e) {
              // ignore parse error for incomplete chunks
            }
          }
        }
      }
      toast.success("Projects generated!", { id: toastId });
    } catch (err) {
      console.error(err);
      toast.error("Failed to generate projects", { id: toastId });
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Personalized Project Generator</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Get AI-tailored portfolio project ideas that bridge your specific skill gaps for your target jobs.
        </p>
      </div>

      <div className="animate-fade-in-up">
        {!result && !isGenerating ? (
          <Card className="border-dashed bg-muted/10 shadow-none">
            <CardContent className="flex flex-col items-center justify-center py-20 text-center">
              <div className="p-5 bg-primary/10 text-primary rounded-full mb-6">
                <Sparkles className="w-10 h-10" />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-foreground">Ready to build your portfolio?</h3>
              <p className="text-muted-foreground max-w-md mx-auto mb-8 text-sm">
                Our AI will analyze your uploaded resumes and saved jobs to recommend projects that prove you have the exact skills employers are looking for.
              </p>
              <Button onClick={generateProjects} className="gap-2">
                <Code className="w-4 h-4" />
                Generate My Projects
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card className="shadow-sm">
            <CardHeader className="border-b flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
              <div>
                <CardTitle className="text-lg">Your Recommended Projects</CardTitle>
                <CardDescription className="text-sm mt-1">Tailored to your career goals</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={generateProjects} disabled={isGenerating}>
                {isGenerating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                {isGenerating ? "Regenerating..." : "Regenerate"}
              </Button>
            </CardHeader>
            <CardContent className="p-6 md:p-8">
              {isGenerating && !result ? (
                <div className="space-y-4">
                  <Skeleton className="h-8 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                  <div className="pt-6 space-y-4">
                    <Skeleton className="h-24 w-full rounded-md" />
                    <Skeleton className="h-24 w-full rounded-md" />
                  </div>
                </div>
              ) : (
                <div 
                  className="prose prose-sm max-w-none prose-p:text-sm prose-li:text-sm"
                  dangerouslySetInnerHTML={{ __html: `<p class="leading-relaxed text-sm">${renderMarkdown(result || "")}</p>` }}
                />
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
