export type AnalysisStatus = "queued" | "running" | "completed" | "failed";
export type SourceType = "github" | "zip";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type FindingCategory =
  | "api_mismatch"
  | "configuration"
  | "secret"
  | "testing"
  | "documentation"
  | "dependency"
  | "deployment"
  | "stack"
  | "architecture"
  // Tolerate future backend categories without a type break.
  | (string & {});

export interface RepositoryIdentity {
  name: string;
  source_type: SourceType;
  url?: string;
}

export interface StackSummary {
  frontend: string[];
  backend: string[];
  database: string[];
  testing: string[];
}

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface AnalysisSummary {
  files_analyzed: number;
  analysis_duration_ms: number;
  findings_by_severity: SeverityCounts;
  readiness_label: string;
}

export interface AnalysisSummaryResponse {
  analysis_id: string;
  status: AnalysisStatus;
  stage?: string;
  repository: RepositoryIdentity;
  stack?: StackSummary;
  summary?: AnalysisSummary;
  created_at?: string;
  completed_at?: string;
  error?: {
    code?: string;
    message: string;
  };
}

export interface EvidenceReference {
  file: string;
  line?: number;
  excerpt: string;
}

export interface Finding {
  id: string;
  severity: Severity;
  category: FindingCategory;
  title: string;
  description: string;
  file?: string;
  line?: number;
  evidence?: string | null;
  confidence: number;
  recommendation: string;
  verification_status: "evidence_backed" | "inferred" | "unknown" | string;
}

export interface FindingsResponse {
  items: Finding[];
  total: number;
}

export type ArchitectureComponentType =
  | "frontend"
  | "backend"
  | "persistence"
  | "external_service"
  | "deployment"
  | "unknown";

export interface ArchitectureComponent {
  id: string;
  type: ArchitectureComponentType;
  label: string;
  evidence_files: string[];
}

export interface ArchitectureConnection {
  source: string;
  target: string;
  label?: string | null;
  evidence_files: string[];
}

export interface ArchitectureResponse {
  components: ArchitectureComponent[];
  connections: ArchitectureConnection[];
}

export interface RoadmapTask {
  id: string;
  priority: "critical" | "high" | "medium" | "low" | string;
  title: string;
  description: string;
  related_finding_ids: string[];
  related_files: string[];
  estimated_complexity: "low" | "medium" | "high" | (string & {});
}

export interface RoadmapResponse {
  items: RoadmapTask[];
}

export interface Citation {
  file: string;
  line?: number;
  excerpt: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  confidence: number;
  insufficient_evidence: boolean;
}

export interface AnalysisReport {
  analysis_id: string;
  status: AnalysisStatus;
  repository: RepositoryIdentity;
  overview: string;
  readiness_label: string;
  stack: StackSummary;
  summary: AnalysisSummary;
  architecture: ArchitectureResponse;
  findings: FindingsResponse;
  roadmap: RoadmapResponse;
  limitations: string[];
  generated_at: string;
}

export interface AnalysisStartResponse {
  analysis_id: string;
  status: AnalysisStatus;
  repository: RepositoryIdentity;
  owner_token?: string | null;
}

export interface ApiErrorShape {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
  message?: string;
}
