import {
  Activity,
  BookOpenText,
  Boxes,
  FileText,
  FolderTree,
  LayoutDashboard,
  MessageSquareText,
  Route,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { BrandMark } from "./icons";
import type { ReactNode } from "react";

export type WorkspaceView = "overview" | "architecture" | "findings" | "roadmap" | "chat" | "report" | "settings";

interface SidebarProps {
  view: WorkspaceView;
  onNavigate: (view: WorkspaceView) => void;
  repositoryName: string;
  onReset: () => void;
}

const navItems: Array<{ id: WorkspaceView; label: string; icon: ReactNode; count?: string }> = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard size={17} /> },
  { id: "architecture", label: "Architecture", icon: <Boxes size={17} /> },
  { id: "findings", label: "Findings", icon: <ShieldCheck size={17} />, count: "09" },
  { id: "roadmap", label: "Recovery roadmap", icon: <Route size={17} /> },
  { id: "chat", label: "Codebase chat", icon: <MessageSquareText size={17} /> },
  { id: "report", label: "Report", icon: <FileText size={17} /> },
];

export function Sidebar({ view, onNavigate, repositoryName, onReset }: SidebarProps) {
  return (
    <aside className="workspace-sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark-wrap"><BrandMark size={34} /></div>
        <div>
          <div className="brand-name">Repo<span>Revive</span></div>
          <div className="brand-subtitle">Repository intelligence</div>
        </div>
      </div>

      <div className="sidebar-context">
        <div className="context-label"><Activity size={12} /> CURRENT ANALYSIS</div>
        <button className="repo-context-button" onClick={() => onNavigate("overview")} aria-label={`Open ${repositoryName} overview`}>
          <span className="repo-context-icon"><FolderTree size={15} /></span>
          <span className="repo-context-name">{repositoryName}</span>
          <span className="status-dot" />
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Analysis sections">
        <div className="nav-section-label">Workspace</div>
        {navItems.map((item) => (
          <button key={item.id} className={`sidebar-nav-item ${view === item.id ? "active" : ""}`} onClick={() => onNavigate(item.id)}>
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
            {item.count && <span className="nav-count">{item.count}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-help-card">
          <span className="help-spark"><BookOpenText size={15} /></span>
          <div>
            <strong>Evidence first</strong>
            <p>Findings link back to the files that support them.</p>
          </div>
        </div>
        <button className={`sidebar-nav-item sidebar-settings ${view === "settings" ? "active" : ""}`} onClick={() => onNavigate("settings")}><Settings2 size={17} /><span>Workspace settings</span></button>
        <button className="new-analysis-button" onClick={onReset}><span>＋</span> Analyze another repo</button>
      </div>
    </aside>
  );
}
