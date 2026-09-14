import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { Toaster } from "react-hot-toast";
import SaaSLayout from "./layouts/SaaSLayout";
import CareerChat from "./pages/CareerChat";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ResumeAnalysisPage from "./pages/ResumeAnalysisPage";
import ResumeUpload from "./pages/ResumeUpload";
import JobAnalyzer from "./pages/JobAnalyzer";
import JobComparisonDashboard from "./pages/JobComparisonDashboard";
import GitHubConnect from "./pages/GitHubConnect";
import CodeReviewDashboard from "./pages/CodeReviewDashboard";
import ProjectGenerator from "./pages/ProjectGenerator";
import LearningRoadmap from "./pages/LearningRoadmap";
import MockInterview from "./pages/MockInterview";

export default function App() {
  return (
    <AuthProvider>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        
        {/* Protected Routes wrapped in SaaSLayout */}
        <Route
          element={
            <ProtectedRoute>
              <SaaSLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/resumes" element={<ResumeUpload />} />
          <Route path="/resumes/:resumeId" element={<ResumeAnalysisPage />} />
          <Route path="/resumes/:resumeId/matches" element={<JobComparisonDashboard />} />
          <Route path="/jobs" element={<JobAnalyzer />} />
          <Route path="/chat" element={<CareerChat />} />
          <Route path="/github/connect" element={<GitHubConnect />} />
          <Route path="/github/dashboard" element={<CodeReviewDashboard />} />
          <Route path="/projects" element={<ProjectGenerator />} />
          <Route path="/roadmap" element={<LearningRoadmap />} />
          <Route path="/interview" element={<MockInterview />} />
          <Route path="/settings" element={<div className="p-8"><h1 className="text-2xl font-bold">Settings (WIP)</h1></div>} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
