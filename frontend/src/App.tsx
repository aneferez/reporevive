import { useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Clock3,
  Code2,
  Copy,
  Database,
  Download,
  ExternalLink,
  FileCode2,
  FileText,
  Filter,
  GitBranch,
  Github,
  Globe2,
  Layers3,
  Link2,
  LockKeyhole,
  Menu,
  MessageSquareText,
  MoreHorizontal,
  Network,
  Plus,
  RefreshCw,
  Rocket,
  Route,
  Search,
  Send,
  Server,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { api, ApiError } from "./lib/api";
import { demoAnalysis, demoArchitecture, demoChat, demoFindings, demoRoadmap } from "./lib/mockData";
import type {
  AnalysisReport,
  AnalysisSummaryResponse,
  ArchitectureResponse,
  ChatResponse,
  Finding,
  FindingsResponse,
  RoadmapResponse,
  Severity,
} from "./types";
import { BrandMark, OrbitSpark } from "./components/icons";
import { SeverityBadge } from "./components/SeverityBadge";
import { Sidebar, type WorkspaceView } from "./components/Sidebar";

type AppView = WorkspaceView | "progress";
type SourceMode = "github" | "zip";
type ProgressStage = "validation" | "inspection" | "stack" | "checks" | "ai" | "report" | "complete";

const progressStages: Array<{ id: ProgressStage; label: string; hint: string }> = [
  { id: "validation", label: "Repository validation", hint: "Confirming a supported public source" },
  { id: "inspection", label: "File-tree inspection", hint: "Mapping source files and project boundaries" },
  { id: "stack", label: "Stack detection", hint: "Identifying frameworks, runtimes, and test tools" },
  { id: "checks", label: "Engineering checks", hint: "Comparing configuration, routes, and documentation" },
  { id: "ai", label: "Grounded reasoning", hint: "Turning evidence into explanations and next steps" },
  { id: "report", label: "Report preparation", hint: "Organizing findings into a recovery plan" },
];

const progressOrder = progressStages.map((stage) => stage.id);
const demoModeEnabled = import.meta.env.VITE_DEMO_MODE === "true";
const demoReport: AnalysisReport = { analysis: demoAnalysis, architecture: demoArchitecture, findings: demoFindings, roadmap: demoRoadmap, limitations: ["This is an opt-in sample analysis for interface review. It is not a live repository result.", "Findings are advisory and do not constitute a formal security audit."] };

function formatDuration(milliseconds = 0) {
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

function formatDate(value?: string) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function readinessLabel(label?: string) {
  return (label ?? "unknown").replaceAll("_", " ");
}

function categoryLabel(category: string) {
  return category.replaceAll("_", " ");
}

function isGithubUrl(value: string) {
  try {
    const parsed = new URL(value.trim());
    const segments = parsed.pathname.split("/").filter(Boolean);
    return parsed.protocol === "https:" && parsed.hostname === "github.com" && segments.length === 2 && !segments.some((segment) => segment === "." || segment === "..");
  } catch {
    return false;
  }
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong while starting the analysis.";
}

function mapBackendStage(stage?: string): ProgressStage | undefined {
  if (!stage) return undefined;
  if (stage === "queued" || stage === "validating" || stage === "intake") return "validation";
  if (stage === "inspecting_files") return "inspection";
  if (stage === "stack_detection") return "stack";
  if (stage === "config_checks" || stage === "api_analysis" || stage === "secret_checks") return "checks";
  if (stage === "ai_analysis") return "ai";
  if (stage === "report_preparation") return "report";
  if (stage === "complete") return "complete";
  return undefined;
}

function App() {
  const [view, setView] = useState<AppView>("overview");
  const [sourceMode, setSourceMode] = useState<SourceMode>("github");
  const [githubUrl, setGithubUrl] = useState("");
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [privacyAcknowledged, setPrivacyAcknowledged] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisSummaryResponse | null>(demoModeEnabled ? demoAnalysis : null);
  const [architecture, setArchitecture] = useState<ArchitectureResponse | null>(demoModeEnabled ? demoArchitecture : null);
  const [findings, setFindings] = useState<FindingsResponse | null>(demoModeEnabled ? demoFindings : null);
  const [roadmap, setRoadmap] = useState<RoadmapResponse | null>(demoModeEnabled ? demoRoadmap : null);
  const [report, setReport] = useState<AnalysisReport | null>(demoModeEnabled ? demoReport : null);
  const [isDemo, setIsDemo] = useState(demoModeEnabled);
  const [progressStage, setProgressStage] = useState<ProgressStage>("validation");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const resetWorkspace = () => {
    setView("overview");
    setAnalysis(null);
    setArchitecture(null);
    setFindings(null);
    setRoadmap(null);
    setReport(null);
    setIsDemo(false);
    setSubmitError(null);
    setProgressStage("validation");
    setMobileNavOpen(false);
  };

  const loadDemo = () => {
    setAnalysis(demoAnalysis);
    setArchitecture(demoArchitecture);
    setFindings(demoFindings);
    setRoadmap(demoRoadmap);
    setReport(demoReport);
    setIsDemo(true);
    setView("overview");
    setSubmitError(null);
  };

  const loadAnalysisDetails = async (analysisId: string, summary: AnalysisSummaryResponse) => {
    const results = await Promise.allSettled([
      api.getArchitecture(analysisId),
      api.getFindings(analysisId),
      api.getRoadmap(analysisId),
      api.getReport(analysisId),
    ]);
    const [architectureResult, findingsResult, roadmapResult, reportResult] = results;
    if (architectureResult.status === "fulfilled") setArchitecture(architectureResult.value);
    if (findingsResult.status === "fulfilled") setFindings(findingsResult.value);
    if (roadmapResult.status === "fulfilled") setRoadmap(roadmapResult.value);
    if (reportResult.status === "fulfilled") setReport(reportResult.value);
    setAnalysis(summary);
  };

  const pollAnalysis = async (analysisId: string) => {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const result = await api.getAnalysis(analysisId);
      const mappedStage = mapBackendStage(result.stage);
      if (mappedStage) setProgressStage(mappedStage);
      if (result.status === "failed") throw new Error(result.error?.message ?? "The repository analysis failed. Please try again.");
      if (result.status === "completed") {
        setProgressStage("complete");
        await loadAnalysisDetails(analysisId, result);
        setView("overview");
        setIsSubmitting(false);
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error("The analysis is taking longer than expected. You can retry from the analysis status page.");
  };

  const submitAnalysis = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    if (sourceMode === "github" && !isGithubUrl(githubUrl)) {
      setSubmitError("Enter a valid public GitHub repository URL, for example https://github.com/owner/repository.");
      return;
    }
    if (sourceMode === "zip" && !zipFile) {
      setSubmitError("Choose a .zip source archive before starting the analysis.");
      return;
    }
    if (zipFile && zipFile.size > 10 * 1024 * 1024) {
      setSubmitError("This archive is larger than the 10 MB MVP limit.");
      return;
    }
    if (!privacyAcknowledged) {
      setSubmitError("Confirm that you are authorized to submit this source and understand that sanitized excerpts may be sent to the configured AI provider.");
      return;
    }
    setIsSubmitting(true);
    setProgressStage("validation");
    setView("progress");
    try {
      const start = sourceMode === "github" ? await api.startGithub(githubUrl.trim()) : await api.uploadZip(zipFile as File);
      setAnalysis(start);
      await pollAnalysis(start.analysis_id);
    } catch (error) {
      setSubmitError(getErrorMessage(error));
      setIsSubmitting(false);
      setView("overview");
    }
  };

  const handleZipChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setZipFile(file);
    setSubmitError(null);
  };

  const deleteAnalysis = async () => {
    if (!analysis) return;
    const confirmed = window.confirm("Delete this analysis and its application-managed data?");
    if (!confirmed) return;
    setIsDeleting(true);
    try {
      if (!isDemo) await api.deleteAnalysis(analysis.analysis_id);
      resetWorkspace();
    } catch (error) {
      setSubmitError(getErrorMessage(error));
    } finally {
      setIsDeleting(false);
    }
  };

  const navigate = (nextView: WorkspaceView) => {
    setView(nextView);
    setMobileNavOpen(false);
  };

  if (!analysis) {
    return <LandingPage githubUrl={githubUrl} setGithubUrl={setGithubUrl} sourceMode={sourceMode} setSourceMode={setSourceMode} zipFile={zipFile} onZipChange={handleZipChange} onSubmit={submitAnalysis} isSubmitting={isSubmitting} submitError={submitError} onLoadDemo={loadDemo} privacyAcknowledged={privacyAcknowledged} setPrivacyAcknowledged={setPrivacyAcknowledged} />;
  }

  if (view === "progress") {
    return <ProgressView repositoryName={analysis.repository.name} stage={progressStage} isSubmitting={isSubmitting} error={submitError} onBack={resetWorkspace} onRetry={() => setView("overview")} />;
  }

  return (
    <div className="app-shell">
      <div className={`mobile-nav-backdrop ${mobileNavOpen ? "visible" : ""}`} onClick={() => setMobileNavOpen(false)} />
      <div className={`mobile-sidebar ${mobileNavOpen ? "visible" : ""}`}>
        <Sidebar view={view} onNavigate={navigate} repositoryName={analysis.repository.name} onReset={resetWorkspace} />
      </div>
      <Sidebar view={view} onNavigate={navigate} repositoryName={analysis.repository.name} onReset={resetWorkspace} />
      <main className="workspace-main">
        <header className="workspace-topbar">
          <button className="mobile-menu-button" onClick={() => setMobileNavOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{analysis.repository.name}</strong></div>
          <div className="topbar-actions">
            {isDemo && <span className="demo-chip"><Sparkles size={13} /> Sample analysis</span>}
            <button className="icon-button" aria-label="Refresh analysis" onClick={() => window.location.reload()}><RefreshCw size={16} /></button>
            <button className="topbar-avatar" aria-label="Account">AG</button>
          </div>
        </header>
        {submitError && <div className="workspace-alert"><AlertCircle size={16} /><span>{submitError}</span><button onClick={() => setSubmitError(null)} aria-label="Dismiss error"><X size={15} /></button></div>}
        {view === "overview" && <OverviewView analysis={analysis} findings={findings} architecture={architecture} onNavigate={navigate} onDelete={deleteAnalysis} isDeleting={isDeleting} />}
        {view === "architecture" && <ArchitectureView analysis={analysis} architecture={architecture} />}
        {view === "findings" && <FindingsView findings={findings} />}
        {view === "roadmap" && <RoadmapView roadmap={roadmap} findings={findings} />}
        {view === "chat" && <ChatView analysisId={analysis.analysis_id} isDemo={isDemo} />}
        {view === "report" && <ReportView analysis={analysis} architecture={architecture} findings={findings} roadmap={roadmap} report={report} />}
      </main>
    </div>
  );
}

interface LandingProps {
  githubUrl: string;
  setGithubUrl: (value: string) => void;
  sourceMode: SourceMode;
  setSourceMode: (value: SourceMode) => void;
  zipFile: File | null;
  onZipChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: FormEvent) => void;
  isSubmitting: boolean;
  submitError: string | null;
  onLoadDemo: () => void;
  privacyAcknowledged: boolean;
  setPrivacyAcknowledged: (value: boolean) => void;
}

function LandingPage({ githubUrl, setGithubUrl, sourceMode, setSourceMode, zipFile, onZipChange, onSubmit, isSubmitting, submitError, onLoadDemo, privacyAcknowledged, setPrivacyAcknowledged }: LandingProps) {
  return (
    <div className="landing-shell">
      <div className="landing-noise" />
      <header className="landing-nav page-container">
        <div className="landing-brand"><div className="landing-brand-mark"><BrandMark size={35} /></div><div><div className="brand-name">Repo<span>Revive</span></div><div className="brand-subtitle">Repository intelligence</div></div></div>
        <div className="landing-nav-right"><span className="nav-status"><span className="status-dot" /> Analysis engine ready</span><button className="ghost-nav-button" onClick={onLoadDemo}>View sample <ArrowUpRight size={15} /></button></div>
      </header>

      <section className="landing-hero page-container">
        <div className="eyebrow"><span className="eyebrow-line" /> AI-assisted repository recovery</div>
        <h1>Turn a tangled codebase<br /><span>into a clear next move.</span></h1>
        <p className="hero-copy">RepoRevive inspects your repository, grounds every finding in source evidence, and turns engineering debt into a practical recovery plan.</p>

        <form className="intake-card" onSubmit={onSubmit}>
          <div className="intake-card-top"><div><span className="intake-label">START AN ANALYSIS</span><h2>Bring your repository into focus.</h2></div><div className="intake-lock"><LockKeyhole size={14} /> source stays unexecuted</div></div>
          <div className="source-tabs" role="tablist" aria-label="Repository source type">
            <button type="button" className={sourceMode === "github" ? "active" : ""} onClick={() => setSourceMode("github")} role="tab" aria-selected={sourceMode === "github"}><Github size={16} /> Public GitHub URL</button>
            <button type="button" className={sourceMode === "zip" ? "active" : ""} onClick={() => setSourceMode("zip")} role="tab" aria-selected={sourceMode === "zip"}><UploadCloud size={16} /> Upload ZIP</button>
          </div>
          {sourceMode === "github" ? (
            <div className="intake-input-row">
              <div className="url-input-wrap"><Github size={17} /><input aria-label="Public GitHub repository URL" value={githubUrl} onChange={(event) => setGithubUrl(event.target.value)} placeholder="https://github.com/owner/repository" /></div>
              <button className="primary-button intake-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? <RefreshCw className="spin" size={17} /> : <span>Analyze repository <ArrowRight size={16} /></span>}</button>
            </div>
          ) : (
            <div className="intake-input-row">
              <label className={`zip-dropzone ${zipFile ? "has-file" : ""}`}>
                <UploadCloud size={20} /><span>{zipFile ? zipFile.name : "Choose a source-code ZIP archive"}</span><small>{zipFile ? `${(zipFile.size / 1024 / 1024).toFixed(2)} MB selected` : "Maximum compressed size: 10 MB"}</small><input type="file" accept=".zip,application/zip" onChange={onZipChange} />
              </label>
              <button className="primary-button intake-submit" type="submit" disabled={isSubmitting || !zipFile}>{isSubmitting ? <RefreshCw className="spin" size={17} /> : <span>Analyze archive <ArrowRight size={16} /></span>}</button>
            </div>
          )}
          {submitError && <div className="intake-error" role="alert"><AlertCircle size={15} /> {submitError}</div>}
          <div className="intake-note"><ShieldCheck size={14} /><span>Only supported source files are inspected. Suspected secrets are masked before any optional AI reasoning.</span><button type="button" className="inline-link" onClick={onLoadDemo}>See how it works <ChevronRight size={13} /></button></div>
          <label className="consent-row"><input type="checkbox" checked={privacyAcknowledged} onChange={(event) => setPrivacyAcknowledged(event.target.checked)} /><span>I’m authorized to submit this source and understand sanitized excerpts may be sent to the configured AI provider.</span></label>
        </form>

        <div className="hero-footnote"><span><CheckCircle2 size={15} /> Public repos and explicit ZIP uploads</span><span><CheckCircle2 size={15} /> No code execution</span><span><CheckCircle2 size={15} /> Evidence-backed output</span></div>
      </section>

      <section className="landing-features page-container">
        <div className="section-intro"><span className="eyebrow-line" /><span>FROM UNCERTAINTY TO MOMENTUM</span></div>
        <div className="feature-grid">
          <FeatureCard icon={<Network size={19} />} number="01" title="See the shape" text="Map frontend, backend, persistence, and deployment relationships from real files." />
          <FeatureCard icon={<ShieldAlert size={19} />} number="02" title="Find the signal" text="Surface configuration gaps, API mismatches, test coverage gaps, and masked secret patterns." />
          <FeatureCard icon={<Route size={19} />} number="03" title="Know the move" text="Leave with a prioritized recovery roadmap and citations you can verify." />
        </div>
      </section>
      <footer className="landing-footer page-container"><span>RepoRevive <span className="footer-muted">/ Understand. Diagnose. Revive.</span></span><span className="footer-muted">Standalone MVP · advisory analysis</span></footer>
    </div>
  );
}

function FeatureCard({ icon, number, title, text }: { icon: React.ReactNode; number: string; title: string; text: string }) {
  return <article className="feature-card"><div className="feature-card-top"><span className="feature-icon">{icon}</span><span className="feature-number">{number}</span></div><h3>{title}</h3><p>{text}</p><ArrowUpRight className="feature-arrow" size={17} /></article>;
}

function ProgressView({ repositoryName, stage, isSubmitting, error, onBack, onRetry }: { repositoryName: string; stage: ProgressStage; isSubmitting: boolean; error: string | null; onBack: () => void; onRetry: () => void }) {
  const currentIndex = progressOrder.indexOf(stage);
  return (
    <div className="progress-shell">
      <div className="progress-orbit orbit-one" /><div className="progress-orbit orbit-two" />
      <header className="progress-header"><button className="back-button" onClick={onBack}><ArrowLeft size={16} /> Back to intake</button><div className="progress-brand"><BrandMark size={30} /><span>Repo<span>Revive</span></span></div><span className="progress-analysis-id">ANALYSIS IN PROGRESS</span></header>
      <main className="progress-content">
        <div className="progress-kicker"><span className="pulse-dot" /> {isSubmitting ? "Reading the repository" : "Analysis paused"}</div>
        <h1>Finding the shape<br /><span>of {repositoryName}.</span></h1>
        <p className="progress-copy">RepoRevive is inspecting supported files without executing the repository. This usually takes less than a minute.</p>
        <div className="progress-card">
          <div className="progress-card-header"><div><span className="intake-label">ANALYSIS PIPELINE</span><h2>{isSubmitting ? "Evidence is coming together" : "Analysis needs attention"}</h2></div><span className="progress-percent">{Math.max(8, Math.min(98, Math.round(((currentIndex + 1) / progressStages.length) * 100)))}%</span></div>
          <div className="progress-track"><span style={{ width: `${Math.max(8, ((currentIndex + 1) / progressStages.length) * 100)}%` }} /></div>
          <div className="progress-stage-list">{progressStages.map((item, index) => { const done = index < currentIndex || stage === "complete"; const active = index === currentIndex && stage !== "complete"; return <div className={`progress-stage ${done ? "done" : ""} ${active ? "active" : ""}`} key={item.id}><span className="stage-state">{done ? <Check size={13} /> : active ? <RefreshCw className="spin" size={13} /> : <span>{String(index + 1).padStart(2, "0")}</span>}</span><div><strong>{item.label}</strong><small>{active ? item.hint : done ? "Evidence captured" : "Queued"}</small></div></div>; })}</div>
          {error && <div className="progress-error"><AlertCircle size={16} /><span>{error}</span><button className="secondary-button" onClick={onRetry}>Return to analysis</button></div>}
        </div>
        <div className="progress-safety"><LockKeyhole size={14} /><span>Privacy boundary</span><p>Only sanitized excerpts may be sent to the configured AI provider. Repository contents are never executed.</p></div>
      </main>
    </div>
  );
}

function WorkspaceHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="workspace-page-header"><div><div className="page-eyebrow"><span className="eyebrow-line" /> {eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-header-actions">{actions}</div>}</div>;
}

function OverviewView({ analysis, findings, architecture, onNavigate, onDelete, isDeleting }: { analysis: AnalysisSummaryResponse; findings: FindingsResponse | null; architecture: ArchitectureResponse | null; onNavigate: (view: WorkspaceView) => void; onDelete: () => void; isDeleting: boolean }) {
  const summary = analysis.summary;
  const stack = analysis.stack;
  const counts = summary?.findings_by_severity ?? { critical: 0, high: 0, medium: 0, low: 0 };
  const totalFindings = findings?.total ?? Object.values(counts).reduce((sum, count) => sum + count, 0);
  return <div className="workspace-page">
    <WorkspaceHeader eyebrow="Analysis overview" title={analysis.repository.name} description={`${analysis.repository.source_type === "github" ? "Public GitHub repository" : "Uploaded ZIP archive"} · analyzed ${formatDate(analysis.completed_at ?? analysis.created_at)}`} actions={<><button className="secondary-button" onClick={() => onNavigate("report")}><FileText size={15} /> View report</button><button className="icon-button border-button" onClick={onDelete} disabled={isDeleting} aria-label="Delete analysis"><Trash2 size={16} /></button></>} />
    <div className="repo-meta-row"><span className="completed-pill"><span className="status-dot" /> Analysis complete</span>{analysis.repository.url && <a href={analysis.repository.url} target="_blank" rel="noreferrer" className="repo-link">{analysis.repository.url.replace("https://", "")} <ExternalLink size={13} /></a>}<span className="repo-meta-spacer" /><span className="meta-label"><Clock3 size={13} /> {formatDuration(summary?.analysis_duration_ms)}</span><span className="meta-label"><FileCode2 size={13} /> {summary?.files_analyzed ?? "—"} files</span></div>
    <section className="overview-hero-card"><div className="overview-hero-copy"><div className="signal-chip"><OrbitSpark /> Heuristic readiness signal</div><h2>{readinessLabel(summary?.readiness_label)}</h2><p>There is a clear recovery path. Start with the two high-severity signals, then make setup and verification reproducible.</p><button className="primary-button" onClick={() => onNavigate("roadmap")}>Open recovery roadmap <ArrowRight size={16} /></button></div><div className="readiness-ring"><div className="ring-glow" /><div className="ring-content"><strong>{totalFindings === 0 ? "100" : Math.max(42, 100 - counts.high * 12 - counts.medium * 4 - counts.low)}<small>%</small></strong><span>readiness<br />heuristic</span></div></div><div className="hero-card-gridline" /></section>
    <div className="metric-grid"><MetricCard label="Files inspected" value={String(summary?.files_analyzed ?? "—")} detail="Supported source files" icon={<FileCode2 size={17} />} tone="neutral" /><MetricCard label="High priority" value={String(counts.high)} detail="Needs attention first" icon={<CircleAlert size={17} />} tone="danger" /><MetricCard label="Architecture" value={String(architecture?.components.length ?? "—")} detail="Detected components" icon={<Network size={17} />} tone="info" /><MetricCard label="Recovery tasks" value={String(roadmapCount(findings, totalFindings))} detail="Prioritized next steps" icon={<Route size={17} />} tone="success" /></div>
    <div className="overview-columns"><section className="panel stack-panel"><PanelHeading eyebrow="Detected stack" title="What the repository is built with" action={<button className="text-button" onClick={() => onNavigate("architecture")}>View architecture <ArrowRight size={14} /></button>} /><div className="stack-groups">{stack && <><StackGroup icon={<Globe2 size={16} />} label="Frontend" values={stack.frontend} /><StackGroup icon={<Server size={16} />} label="Backend" values={stack.backend} /><StackGroup icon={<Database size={16} />} label="Persistence" values={stack.database} /><StackGroup icon={<CheckCircle2 size={16} />} label="Testing" values={stack.testing} /></>}{!stack && <EmptyState icon={<Layers3 size={18} />} title="Stack data is not available" text="The backend has not returned stack evidence for this analysis." />}</div></section><section className="panel signal-panel"><PanelHeading eyebrow="Finding signals" title="Where to focus next" action={<button className="text-button" onClick={() => onNavigate("findings")}>All findings <ArrowRight size={14} /></button>} /><div className="signal-total"><strong>{totalFindings}</strong><span>evidence-backed signals</span></div><div className="severity-bars">{(["critical", "high", "medium", "low"] as Severity[]).map((severity) => <SeverityBar key={severity} severity={severity} count={counts[severity]} total={Math.max(totalFindings, 1)} />)}</div><div className="signal-footnote"><ShieldCheck size={14} /> Findings remain advisory; verify before changing code.</div></section></div>
    <section className="panel focus-panel"><PanelHeading eyebrow="Fast read" title="Start with the sharp edges" action={<button className="text-button" onClick={() => onNavigate("findings")}>Open findings <ArrowRight size={14} /></button>} /><div className="focus-list">{(findings?.items ?? []).filter((finding) => finding.severity === "high" || finding.severity === "critical").slice(0, 3).map((finding) => <FocusFinding finding={finding} key={finding.id} onClick={() => onNavigate("findings")} />)}{!(findings?.items ?? []).some((finding) => finding.severity === "high" || finding.severity === "critical") && <EmptyState icon={<CircleCheck size={18} />} title="No urgent findings" text="The current report has no critical or high-severity signals." />}</div></section>
    <div className="workspace-disclaimer"><ShieldCheck size={14} /><span>RepoRevive is an advisory analysis tool. Readiness is a heuristic, not a formal security assessment.</span></div>
  </div>;
}

function roadmapCount(findings: FindingsResponse | null, fallback: number) {
  if (!findings) return fallback;
  return Math.max(1, Math.ceil(findings.total * 0.55));
}

function MetricCard({ label, value, detail, icon, tone }: { label: string; value: string; detail: string; icon: React.ReactNode; tone: string }) {
  return <div className={`metric-card tone-${tone}`}><div className="metric-icon">{icon}</div><div className="metric-label">{label}</div><strong>{value}</strong><span>{detail}</span></div>;
}

function StackGroup({ icon, label, values }: { icon: React.ReactNode; label: string; values: string[] }) {
  return <div className="stack-group"><div className="stack-group-label">{icon}<span>{label}</span></div><div className="stack-values">{values.length ? values.map((value) => <span className="tech-chip" key={value}>{value}</span>) : <span className="unknown-chip">Unknown</span>}</div></div>;
}

function SeverityBar({ severity, count, total }: { severity: Severity; count: number; total: number }) {
  const names = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
  return <div className="severity-bar-row"><span className={`severity-dot dot-${severity}`} /><span className="severity-name">{names[severity]}</span><div className="severity-track"><span className={`severity-fill fill-${severity}`} style={{ width: `${Math.max(count ? 5 : 0, (count / total) * 100)}%` }} /></div><strong>{count}</strong></div>;
}

function PanelHeading({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return <div className="panel-heading"><div><div className="panel-eyebrow">{eyebrow}</div><h2>{title}</h2></div>{action}</div>;
}

function FocusFinding({ finding, onClick }: { finding: Finding; onClick: () => void }) {
  return <button className="focus-finding" onClick={onClick}><SeverityBadge severity={finding.severity} /><div className="focus-finding-main"><strong>{finding.title}</strong><span><Terminal size={12} /> {finding.file ?? "Repository evidence"}{finding.line ? `:${finding.line}` : ""}</span></div><ChevronRight size={16} /></button>;
}

function ArchitectureView({ analysis, architecture }: { analysis: AnalysisSummaryResponse; architecture: ArchitectureResponse | null }) {
  return <div className="workspace-page"><WorkspaceHeader eyebrow="System map" title="Architecture" description="The relationships RepoRevive could confirm from repository evidence." actions={<span className="confidence-note"><ShieldCheck size={14} /> Evidence-linked components</span>} /><div className="architecture-layout"><section className="panel architecture-map-panel"><div className="architecture-map-header"><div><div className="panel-eyebrow">Relationship view</div><h2>{architecture?.components.length ?? 0} components detected</h2></div><span className="map-legend"><span className="legend-line" /> confirmed relationship</span></div>{architecture ? <div className="architecture-map"><div className="map-grid" /><div className="architecture-nodes">{architecture.components.map((component, index) => <ArchitectureNode key={component.id} component={component} index={index} />)}</div><div className="connection-list">{architecture.connections.map((connection) => <div className="connection-row" key={`${connection.source}-${connection.target}`}><span className="connection-pill">{connection.source}</span><ArrowRight size={14} /><span className="connection-pill">{connection.target}</span><span className="connection-label">{connection.label}</span></div>)}</div></div> : <EmptyState icon={<Network size={19} />} title="Architecture is still loading" text={`We are waiting for the analysis service to return the component map for ${analysis.repository.name}.`} />}</section><section className="panel evidence-panel"><PanelHeading eyebrow="Architecture evidence" title="Why these components appear" /><div className="evidence-component-list">{architecture?.components.map((component) => <div className="evidence-component" key={component.id}><div className={`component-type-icon type-${component.type}`}><ArchitectureIcon type={component.type} /></div><div><strong>{component.label}</strong><span>{component.evidence_files.length} evidence file{component.evidence_files.length === 1 ? "" : "s"}</span></div><ChevronRight size={15} /></div>)}</div><div className="unknown-note"><CircleAlert size={14} /><span>Unknown or inferred components are intentionally kept visible instead of being presented as fact.</span></div></section></div></div>;
}

function ArchitectureIcon({ type }: { type: string }) {
  if (type === "frontend") return <Globe2 size={17} />;
  if (type === "backend") return <Server size={17} />;
  if (type === "persistence") return <Database size={17} />;
  if (type === "deployment") return <Rocket size={17} />;
  return <Network size={17} />;
}

function ArchitectureNode({ component, index }: { component: NonNullable<ArchitectureResponse["components"]>[number]; index: number }) {
  return <div className={`architecture-node node-${index % 4} type-${component.type}`}><div className="node-icon"><ArchitectureIcon type={component.type} /></div><div><strong>{component.label}</strong><small>{component.evidence_files[0] ?? "Evidence unavailable"}</small></div></div>;
}

function FindingsView({ findings }: { findings: FindingsResponse | null }) {
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [category, setCategory] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const items = findings?.items ?? [];
  const categories = Array.from(new Set(items.map((finding) => finding.category)));
  const filtered = useMemo(() => items.filter((finding) => {
    const matchesQuery = !query || [finding.title, finding.description, finding.file, finding.evidence].filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase());
    const matchesSeverity = severity === "all" || finding.severity === severity;
    const matchesCategory = category === "all" || finding.category === category;
    return matchesQuery && matchesSeverity && matchesCategory;
  }), [items, query, severity, category]);
  return <div className="workspace-page"><WorkspaceHeader eyebrow="Evidence-backed signals" title="Findings" description="Every signal includes source evidence, confidence, and a recommended next action." actions={<span className="confidence-note"><ShieldCheck size={14} /> {items.length} total findings</span>} /><div className="filter-toolbar"><div className="finding-search"><Search size={16} /><input aria-label="Search findings" placeholder="Search title, file, or evidence" value={query} onChange={(event) => setQuery(event.target.value)} />{query && <button onClick={() => setQuery("")} aria-label="Clear search"><X size={14} /></button>}</div><div className="select-wrap"><Filter size={14} /><select value={severity} onChange={(event) => setSeverity(event.target.value as Severity | "all")} aria-label="Filter findings by severity"><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><ChevronDown size={14} /></div><div className="select-wrap category-select"><select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter findings by category"><option value="all">All categories</option>{categories.map((item) => <option key={item} value={item}>{categoryLabel(item)}</option>)}</select><ChevronDown size={14} /></div></div><div className="findings-list">{filtered.map((finding) => <FindingCard key={finding.id} finding={finding} expanded={expanded === finding.id} onToggle={() => setExpanded(expanded === finding.id ? null : finding.id)} />)}{filtered.length === 0 && <div className="panel empty-results"><Search size={21} /><h2>No matching findings</h2><p>Try a different search term or clear the filters.</p><button className="secondary-button" onClick={() => { setQuery(""); setSeverity("all"); setCategory("all"); }}>Clear filters</button></div>}</div><div className="workspace-disclaimer"><ShieldCheck size={14} /><span>Potential exposure findings are masked and should be independently verified before remediation.</span></div></div>;
}

function FindingCard({ finding, expanded, onToggle }: { finding: Finding; expanded: boolean; onToggle: () => void }) {
  return <article className={`finding-card ${expanded ? "expanded" : ""}`}><button className="finding-card-header" onClick={onToggle} aria-expanded={expanded}><div className="finding-card-title"><SeverityBadge severity={finding.severity} /><span className="category-label">{categoryLabel(finding.category)}</span><h2>{finding.title}</h2></div><div className="finding-card-meta"><span className="confidence-score">{Math.round(finding.confidence * 100)}% confidence</span><ChevronDown className={`expand-chevron ${expanded ? "rotated" : ""}`} size={17} /></div></button><div className="finding-summary"><p>{finding.description}</p><span className="file-reference"><FileCode2 size={13} /> {finding.file ?? "Repository-level evidence"}{finding.line ? `:${finding.line}` : ""}</span></div>{expanded && <div className="finding-expanded"><div className="evidence-block"><div className="evidence-label"><Terminal size={13} /> Source evidence</div><code>{finding.evidence}</code></div><div className="recommendation-block"><div className="evidence-label"><Route size={13} /> Recommended next action</div><p>{finding.recommendation}</p></div><div className="verification-row"><span><CheckCircle2 size={14} /> {finding.verification_status === "evidence_backed" ? "Evidence-backed finding" : `${finding.verification_status} signal`}</span><button className="copy-button" onClick={() => navigator.clipboard?.writeText(`${finding.file ?? "Repository"}${finding.line ? `:${finding.line}` : ""}\n${finding.evidence}`)}><Copy size={13} /> Copy evidence</button></div></div>}</article>;
}

function RoadmapView({ roadmap, findings }: { roadmap: RoadmapResponse | null; findings: FindingsResponse | null }) {
  const groups = ["high", "medium", "low"];
  return <div className="workspace-page"><WorkspaceHeader eyebrow="Prioritized recovery" title="Roadmap" description="A sequence of practical moves, ordered around blockers, safety, and release readiness." actions={<span className="confidence-note"><Route size={14} /> {roadmap?.items.length ?? 0} tasks</span>} /><div className="roadmap-intro panel"><div className="roadmap-intro-icon"><Route size={21} /></div><div><h2>Make the next change count.</h2><p>Start with work that unblocks the product or reduces risk. Optional improvements come after the recovery spine is stable.</p></div><div className="roadmap-progress"><span>Recovery sequence</span><strong>01 <small>/ {roadmap?.items.length.toString().padStart(2, "0") ?? "00"}</small></strong></div></div><div className="roadmap-columns">{groups.map((priority) => { const tasks = (roadmap?.items ?? []).filter((task) => task.priority === priority); return <section className="roadmap-group" key={priority}><div className="roadmap-group-heading"><span className={`priority-marker marker-${priority}`} /> <h2>{priority === "high" ? "Immediate attention" : priority === "medium" ? "Stabilize the path" : "Polish and protect"}</h2><span className="task-count">{tasks.length.toString().padStart(2, "0")}</span></div>{tasks.map((task, index) => <RoadmapTaskCard key={task.id} task={task} index={index} findings={findings} />)}{tasks.length === 0 && <div className="roadmap-empty">No tasks in this tier.</div>}</section>; })}</div><div className="workspace-disclaimer"><CircleAlert size={14} /><span>Complexity estimates are directional and should be refined after the related files are reviewed.</span></div></div>;
}

function RoadmapTaskCard({ task, index, findings }: { task: NonNullable<RoadmapResponse["items"]>[number]; index: number; findings: FindingsResponse | null }) {
  const [open, setOpen] = useState(false);
  return <article className={`roadmap-task-card ${open ? "open" : ""}`}><button onClick={() => setOpen(!open)} className="roadmap-task-header" aria-expanded={open}><span className="task-index">{String(index + 1).padStart(2, "0")}</span><span className="task-title-wrap"><strong>{task.title}</strong><span>{task.estimated_complexity} complexity · {task.related_finding_ids.length} related signal{task.related_finding_ids.length === 1 ? "" : "s"}</span></span><ChevronDown size={16} className={open ? "rotated" : ""} /></button>{open && <div className="roadmap-task-detail"><p>{task.description}</p><div className="related-files">{task.related_files.map((file) => <span key={file}><FileCode2 size={12} /> {file}</span>)}</div>{task.related_finding_ids.length > 0 && <div className="related-findings"><span>Related evidence</span>{task.related_finding_ids.map((id) => { const finding = findings?.items.find((item) => item.id === id); return <span className="related-finding-chip" key={id}>{finding?.title ?? id}</span>; })}</div>}</div>}</article>;
}

function ChatView({ analysisId, isDemo }: { analysisId: string; isDemo: boolean }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<ChatResponse | null>(isDemo ? demoChat : null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const suggestedQuestions = ["Why does the job search feature appear incomplete?", "What should I fix before deployment?", "Which files support the highest-risk finding?"];
  const ask = async (event?: FormEvent, suggestedQuestion?: string) => {
    event?.preventDefault();
    const value = (suggestedQuestion ?? question).trim();
    if (!value || isLoading) return;
    setIsLoading(true); setError(null);
    try { setAnswer(isDemo ? demoChat : await api.askQuestion(analysisId, value)); setQuestion(""); } catch (err) { setError(getErrorMessage(err)); } finally { setIsLoading(false); }
  };
  return <div className="workspace-page chat-page"><WorkspaceHeader eyebrow="Repository-grounded answers" title="Codebase chat" description="Ask a question and get an answer anchored to the files RepoRevive inspected." actions={<span className="confidence-note"><MessageSquareText size={14} /> Citations required</span>} /><div className="chat-layout"><section className="panel chat-panel"><div className="chat-panel-header"><div className="assistant-avatar"><OrbitSpark /></div><div><strong>RepoRevive assistant</strong><span>Grounded in inspected repository context</span></div><span className="online-indicator"><span className="status-dot" /> ready</span></div>{answer ? <div className="answer-card"><div className="answer-label"><Sparkles size={14} /> Analysis answer <span>{Math.round(answer.confidence * 100)}% confidence</span></div><p>{answer.answer}</p>{answer.insufficient_evidence && <div className="insufficient-note"><CircleAlert size={14} /> The repository did not provide enough evidence to make this claim confidently.</div>}{answer.citations.length > 0 && <div className="citation-list"><div className="citation-heading">Source citations</div>{answer.citations.map((citation, index) => <div className="citation-item" key={`${citation.file}-${index}`}><span className="citation-number">0{index + 1}</span><div><strong>{citation.file}{citation.line ? `:${citation.line}` : ""}</strong><code>{citation.excerpt}</code></div><ExternalLink size={14} /></div>)}</div>}</div> : <div className="chat-empty"><div className="chat-empty-orbit"><OrbitSpark /></div><h2>Ask the repository a question.</h2><p>Try one of the prompts below, or ask about a file, flow, risk, or next step.</p><div className="suggested-list">{suggestedQuestions.map((item) => <button onClick={() => void ask(undefined, item)} key={item}>{item}<ArrowUpRight size={14} /></button>)}</div></div>}{error && <div className="chat-error"><AlertCircle size={14} /> {error}</div>}<form className="chat-input-row" onSubmit={ask}><input aria-label="Ask a repository question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about a file, flow, or finding..." /><button type="submit" disabled={isLoading || !question.trim()} aria-label="Send question">{isLoading ? <RefreshCw className="spin" size={17} /> : <Send size={17} />}</button></form></section><aside className="chat-aside"><div className="panel chat-guidance"><div className="panel-eyebrow">Good questions look like</div><h2>Specific, source-shaped, useful.</h2><div className="guidance-list"><Guidance icon={<FileCode2 size={15} />} text="Why is this file involved in the deployment issue?" /><Guidance icon={<GitBranch size={15} />} text="Where does the frontend call this backend route?" /><Guidance icon={<Route size={15} />} text="What should I do before I add a new feature?" /></div></div><div className="panel privacy-card"><LockKeyhole size={16} /><strong>Grounding boundary</strong><p>Answers can only use context retrieved from this analysis. When evidence is thin, the assistant says so.</p></div></aside></div></div>;
}

function Guidance({ icon, text }: { icon: React.ReactNode; text: string }) {
  return <div className="guidance-item"><span>{icon}</span><p>{text}</p></div>;
}

function ReportView({ analysis, architecture, findings, roadmap, report }: { analysis: AnalysisSummaryResponse; architecture: ArchitectureResponse | null; findings: FindingsResponse | null; roadmap: RoadmapResponse | null; report: AnalysisReport | null }) {
  const download = () => {
    const payload = report ?? { analysis, architecture, findings, roadmap };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = `${analysis.repository.name}-reporevive-report.json`; link.click(); URL.revokeObjectURL(url);
  };
  return <div className="workspace-page report-page"><WorkspaceHeader eyebrow="Shareable analysis" title="Report" description="A print-friendly snapshot of the repository’s current recovery position." actions={<><button className="secondary-button" onClick={() => window.print()}><FileText size={15} /> Print report</button><button className="primary-button" onClick={download}><Download size={15} /> Download JSON</button></>} /><article className="report-document"><div className="report-cover"><div className="report-cover-brand"><BrandMark size={34} /><div className="brand-name">Repo<span>Revive</span></div></div><div className="report-cover-kicker">REPOSITORY RECOVERY REPORT</div><h2>{analysis.repository.name}</h2><p>{analysis.repository.url ?? "Uploaded source archive"}</p><div className="report-cover-meta"><span>Analyzed {formatDate(analysis.completed_at ?? analysis.created_at)}</span><span>{analysis.summary?.files_analyzed ?? "—"} files inspected</span><span>Advisory output</span></div></div><div className="report-section"><div className="report-section-label">01 / Executive summary</div><div className="report-summary-grid"><div><h3>{readinessLabel(analysis.summary?.readiness_label)}</h3><p>RepoRevive detected {findings?.total ?? 0} evidence-backed signals across the inspected repository. The recovery sequence starts with high-priority API and security work, followed by reproducibility and test coverage.</p></div><div className="report-count-grid">{(["critical", "high", "medium", "low"] as Severity[]).map((severity) => <div key={severity}><span className={`severity-dot dot-${severity}`} /><strong>{analysis.summary?.findings_by_severity[severity] ?? 0}</strong><small>{severity}</small></div>)}</div></div></div><div className="report-section"><div className="report-section-label">02 / Stack & architecture</div><div className="report-two-col"><div className="report-stack-list">{Object.entries(analysis.stack ?? {}).map(([label, values]) => <div className="report-stack-row" key={label}><span>{label}</span><strong>{(values as string[]).join(" · ") || "Unknown"}</strong></div>)}</div><div className="report-components">{architecture?.components.map((component) => <span key={component.id}><ArchitectureIcon type={component.type} /> {component.label}</span>)}</div></div></div><div className="report-section"><div className="report-section-label">03 / Recovery roadmap</div><div className="report-task-list">{roadmap?.items.slice(0, 5).map((task, index) => <div className="report-task-row" key={task.id}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{task.title}</strong><p>{task.description}</p></div><em>{task.priority}</em></div>)}</div></div><div className="report-section report-limitations"><div className="report-section-label">04 / Known limitations</div><ul>{(report?.limitations ?? ["Repository contents were inspected but not executed.", "Findings are advisory and should be verified by an engineer with repository context.", "The MVP supports public repositories and explicit ZIP uploads only."]).map((item) => <li key={item}>{item}</li>)}</ul></div><div className="report-footer"><span>RepoRevive · Understand. Diagnose. Revive.</span><span>Generated from evidence available at analysis time</span></div></article></div>;
}

function EmptyState({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div className="empty-state"><span>{icon}</span><h3>{title}</h3><p>{text}</p></div>;
}

export default App;
