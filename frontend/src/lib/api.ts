import type {
  AnalysisReport,
  AnalysisStartResponse,
  AnalysisSummaryResponse,
  ArchitectureResponse,
  ChatResponse,
  FindingsResponse,
  RoadmapResponse,
} from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const OWNER_TOKEN_HEADER = "X-Owner-Token";

export class ApiError extends Error {
  code?: string;
  status: number;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit, ownerToken?: string | null): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
        ...(ownerToken ? { [OWNER_TOKEN_HEADER]: ownerToken } : {}),
      },
    });
  } catch {
    throw new ApiError("The analysis service could not be reached. Check the backend URL and try again.", 0);
  }

  const body = (await response.json().catch(() => null)) as { error?: { message?: string; code?: string }; message?: string } | null;
  if (!response.ok) {
    throw new ApiError(
      body?.error?.message ?? body?.message ?? `The analysis service returned ${response.status}.`,
      response.status,
      body?.error?.code,
    );
  }
  return body as T;
}

export const api = {
  startGithub(repositoryUrl: string) {
    return request<AnalysisStartResponse>("/api/repositories/analyze", {
      method: "POST",
      body: JSON.stringify({ repository_url: repositoryUrl }),
    });
  },

  uploadZip(file: File) {
    const form = new FormData();
    form.append("file", file);
    return request<AnalysisStartResponse>("/api/repositories/upload", {
      method: "POST",
      body: form,
    });
  },

  getAnalysis(analysisId: string, ownerToken?: string | null) {
    return request<AnalysisSummaryResponse>(`/api/analysis/${encodeURIComponent(analysisId)}`, undefined, ownerToken);
  },

  getArchitecture(analysisId: string, ownerToken?: string | null) {
    return request<ArchitectureResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/architecture`, undefined, ownerToken);
  },

  getFindings(analysisId: string, ownerToken?: string | null) {
    return request<FindingsResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/findings`, undefined, ownerToken);
  },

  getRoadmap(analysisId: string, ownerToken?: string | null) {
    return request<RoadmapResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/roadmap`, undefined, ownerToken);
  },

  askQuestion(analysisId: string, question: string, ownerToken?: string | null) {
    return request<ChatResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/chat`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }, ownerToken);
  },

  getReport(analysisId: string, ownerToken?: string | null) {
    return request<AnalysisReport>(`/api/analysis/${encodeURIComponent(analysisId)}/report`, undefined, ownerToken);
  },

  deleteAnalysis(analysisId: string, ownerToken?: string | null) {
    return request<void>(`/api/analysis/${encodeURIComponent(analysisId)}`, { method: "DELETE" }, ownerToken);
  },
};

export const apiConfig = {
  baseUrl: API_BASE_URL,
};
