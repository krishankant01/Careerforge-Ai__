import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { extractErrorMessage } from "../services/api";
import { listResumes, uploadResume } from "../services/resumeService";
import type { Resume } from "../types/resume";
import { Card, CardContent } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import toast from "react-hot-toast";
import { UploadCloud, FileText, ChevronRight, AlertCircle } from "lucide-react";

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

export default function ResumeUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [resumes, setResumes] = useState<Resume[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const refreshList = useCallback(async () => {
    try {
      const data = await listResumes();
      setResumes(data);
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  async function handleFile(file: File) {
    const hasAllowedExtension = ALLOWED_EXTENSIONS.some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    );
    if (!hasAllowedExtension) {
      toast.error("Only PDF and DOCX files are supported.");
      return;
    }

    setIsUploading(true);
    const toastId = toast.loading("Uploading and analyzing resume...");

    try {
      const resume = await uploadResume(file);
      toast.success("Resume processed successfully!", { id: toastId });
      if (resume.status === "completed") {
        navigate(`/resumes/${resume.id}`);
      } else {
        await refreshList();
      }
    } catch (err) {
      toast.error(extractErrorMessage(err), { id: toastId });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-10">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Resumes</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Upload and analyze your resumes for ATS optimization.
          </p>
        </div>
      </div>

      <Card className={`border-dashed border-2 transition-all duration-200 ${isDragOver ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-muted/30 hover:border-muted-foreground/30"}`}>
        <CardContent className="p-0">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              const file = e.dataTransfer.files?.[0];
              if (file) handleFile(file);
            }}
            onClick={() => fileInputRef.current?.click()}
            className="flex cursor-pointer flex-col items-center justify-center py-12 px-4 text-center rounded-xl"
          >
            <div className={`p-4 rounded-full mb-4 transition-all duration-200 ${isDragOver ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground group-hover:bg-muted/80'}`}>
              <UploadCloud className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-medium text-foreground mb-1">
              {isUploading ? "Processing your resume..." : "Drop your resume here, or click to browse"}
            </h3>
            <p className="text-sm text-muted-foreground">Supports PDF and DOCX formats up to 5MB</p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              disabled={isUploading}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">Recent Resumes</h2>

        {isLoadingList ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}
          </div>
        ) : resumes.length === 0 ? (
          <Card className="border-dashed border-border shadow-none bg-muted/10">
            <CardContent className="flex flex-col items-center justify-center py-10 text-center">
              <FileText className="w-10 h-10 text-muted-foreground mb-3 opacity-50" />
              <p className="text-sm font-medium text-foreground">No resumes uploaded yet</p>
              <p className="text-xs text-muted-foreground mt-1">Upload your first resume above to get started.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="rounded-md border bg-card">
            <div className="divide-y divide-border">
              {resumes.map((resume) => (
                <Link key={resume.id} to={`/resumes/${resume.id}`} className="flex flex-col sm:flex-row sm:items-center p-4 hover:bg-muted/30 transition-colors gap-4">
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <div className="p-2 bg-primary/10 text-primary rounded">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {resume.original_filename}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(resume.created_at).toLocaleDateString(undefined, {
                          year: 'numeric', month: 'short', day: 'numeric',
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </p>
                      {resume.status === "failed" && resume.failure_reason && (
                        <p className="mt-2 text-xs text-destructive flex items-center gap-1 bg-destructive/10 w-fit px-2 py-0.5 rounded">
                          <AlertCircle className="w-3 h-3" />
                          {resume.failure_reason}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center justify-between sm:justify-end gap-6 sm:w-48">
                    <StatusBadge status={resume.status} />
                    <ChevronRight className="w-5 h-5 text-muted-foreground" />
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
