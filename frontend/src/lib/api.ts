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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
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

  getAnalysis(analysisId: string) {
    return request<AnalysisSummaryResponse>(`/api/analysis/${encodeURIComponent(analysisId)}`);
  },

  getArchitecture(analysisId: string) {
    return request<ArchitectureResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/architecture`);
  },

  getFindings(analysisId: string) {
    return request<FindingsResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/findings`);
  },

  getRoadmap(analysisId: string) {
    return request<RoadmapResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/roadmap`);
  },

  askQuestion(analysisId: string, question: string) {
    return request<ChatResponse>(`/api/analysis/${encodeURIComponent(analysisId)}/chat`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
  },

  getReport(analysisId: string) {
    return request<AnalysisReport>(`/api/analysis/${encodeURIComponent(analysisId)}/report`);
  },

  deleteAnalysis(analysisId: string) {
    return request<void>(`/api/analysis/${encodeURIComponent(analysisId)}`, { method: "DELETE" });
  },
};

export const apiConfig = {
  baseUrl: API_BASE_URL,
};
