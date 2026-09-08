import type {
  AnalyzeCreatorResponse,
  ContentItemCreate,
  CreatorCreateResponse,
  CreatorRead,
  CreatorStateSnapshot,
  GenerateOpportunitiesResponse,
  OpportunityRead,
  OpportunityStatus,
  ResearchSignalCreate,
  ResearchSignalRead,
} from "./types";
import { getSession } from "./session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = getSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (session) {
    headers["X-Debug-User-Id"] = session.userId;
  }

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export interface CreateCreatorPayload {
  email: string;
  name: string;
  niche?: string;
  sub_niche?: string;
  geography?: string;
  business_model?: string;
  monetization_model?: string;
}

export function createCreator(payload: CreateCreatorPayload) {
  return request<CreatorCreateResponse>("/creators", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCreator(creatorId: string) {
  return request<CreatorRead>(`/creators/${creatorId}`);
}

export function getCreatorState(creatorId: string) {
  return request<CreatorStateSnapshot>(`/creators/${creatorId}/state`);
}

export function analyzeCreator(creatorId: string) {
  return request<AnalyzeCreatorResponse>(`/creators/${creatorId}/analyze`, { method: "POST" });
}

export function ingestContent(creatorId: string, payload: ContentItemCreate) {
  return request(`/creators/${creatorId}/content`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createResearchSignal(creatorId: string, payload: ResearchSignalCreate) {
  return request<ResearchSignalRead>(`/creators/${creatorId}/research-signals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listResearchSignals(creatorId: string) {
  return request<ResearchSignalRead[]>(`/creators/${creatorId}/research-signals`);
}

export function generateOpportunities(creatorId: string) {
  return request<GenerateOpportunitiesResponse>(`/creators/${creatorId}/opportunities/generate`, {
    method: "POST",
  });
}

export function listOpportunities(creatorId: string) {
  return request<OpportunityRead[]>(`/creators/${creatorId}/opportunities`);
}

export function updateOpportunityStatus(creatorId: string, opportunityId: string, status: OpportunityStatus) {
  return request<OpportunityRead>(`/creators/${creatorId}/opportunities/${opportunityId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
