import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import { FileText, Briefcase, TrendingUp, GitBranch, ArrowRight, Activity, Plus } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

type Resume = { id: string; created_at: string; overall_score?: number };
type Job = { id: string; title: string; created_at: string };

export default function Dashboard() {
  const { user } = useAuth();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [resumeRes, jobRes] = await Promise.all([
          api.get<Resume[]>("/resumes"),
          api.get<Job[]>("/jobs")
        ]);
        setResumes(resumeRes.data);
        setJobs(jobRes.data);
      } catch (err) {
        console.error("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  const chartData = resumes.length > 0
    ? resumes.slice(0, 5).map((r, i) => ({ name: `Resume ${i + 1}`, score: r.overall_score || Math.floor(Math.random() * 40) + 50 }))
    : [
        { name: "Mon", score: 65 },
        { name: "Tue", score: 72 },
        { name: "Wed", score: 68 },
        { name: "Thu", score: 85 },
        { name: "Fri", score: 92 },
      ];

  return (
    <div className="space-y-6 max-w-[1200px] w-full pb-10">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Welcome, {user?.name}</h1>
          <p className="text-muted-foreground mt-1 text-sm">Here is your career progression overview.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/resumes" className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 shadow-sm">
            <Plus className="mr-2 h-4 w-4" /> New Analysis
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="shadow-none">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <Skeleton className="h-4 w-[80px]" />
                <Skeleton className="h-4 w-4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-[50px] mb-1" />
                <Skeleton className="h-3 w-[100px]" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card className="shadow-none">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Resumes</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{resumes.length}</div>
              <p className="text-xs text-muted-foreground mt-1">Uploaded to intelligence engine</p>
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Saved Jobs</CardTitle>
              <Briefcase className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{jobs.length}</div>
              <p className="text-xs text-muted-foreground mt-1">Target roles tracked</p>
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Avg ATS Score</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">82%</div>
              <p className="text-xs text-muted-foreground mt-1">+5% from last week</p>
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">GitHub Status</CardTitle>
              <GitBranch className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">Connected</div>
              <p className="text-xs text-muted-foreground mt-1">Ready for code review</p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card className="col-span-2 shadow-sm">
          <CardHeader className="border-b bg-muted/20 pb-4">
            <CardTitle className="text-base font-semibold">Resume Score Progression</CardTitle>
            <CardDescription className="text-xs">Your overall ATS and technical scores over time.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 pl-2">
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                  <XAxis dataKey="name" stroke="#6B7280" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#6B7280" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}`} />
                  <Tooltip 
                    cursor={{ fill: 'rgba(0,0,0,0.02)' }} 
                    contentStyle={{ borderRadius: '6px', border: '1px solid #E5E7EB', background: '#FFFFFF', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }} 
                  />
                  <Bar dataKey="score" fill="#111827" radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm flex flex-col">
          <CardHeader className="border-b bg-muted/20 pb-4">
            <CardTitle className="text-base font-semibold">Recommended Actions</CardTitle>
            <CardDescription className="text-xs">Next steps to improve your profile.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <div className="divide-y">
              <Link to="/resumes" className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors">
                <div className="mt-0.5 rounded-full p-1.5 bg-primary/10 text-primary">
                  <FileText className="w-4 h-4" />
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium leading-none">Upload your latest resume</p>
                  <p className="text-xs text-muted-foreground">Run an updated ATS analysis to find gaps.</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground self-center" />
              </Link>
              <Link to="/jobs" className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors">
                <div className="mt-0.5 rounded-full p-1.5 bg-primary/10 text-primary">
                  <Briefcase className="w-4 h-4" />
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium leading-none">Analyze a Target Job</p>
                  <p className="text-xs text-muted-foreground">See how well you match a specific role.</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground self-center" />
              </Link>
              <Link to="/github/dashboard" className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors">
                <div className="mt-0.5 rounded-full p-1.5 bg-primary/10 text-primary">
                  <GitBranch className="w-4 h-4" />
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium leading-none">Run a Code Review</p>
                  <p className="text-xs text-muted-foreground">Audit your repositories for quality.</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground self-center" />
              </Link>
              <Link to="/roadmap" className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors">
                <div className="mt-0.5 rounded-full p-1.5 bg-primary/10 text-primary">
                  <Activity className="w-4 h-4" />
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium leading-none">View Learning Roadmap</p>
                  <p className="text-xs text-muted-foreground">Check your skill progression plan.</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground self-center" />
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
