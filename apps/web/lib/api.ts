import type {
  AnalyzeAudienceResponse,
  AnalyzeCreatorResponse,
  AudienceSignalCreate,
  AudienceSignalRead,
  ContentDetailRead,
  ContentItemCreate,
  ContentItemRead,
  CreatorCreateResponse,
  CreatorRead,
  CreatorStateSnapshot,
  GenerateBriefResponse,
  GenerateOpportunitiesResponse,
  GenerateScriptResponse,
  GenerateStrategyResponse,
  OpportunityRead,
  OpportunityStatus,
  ResearchSignalCreate,
  ResearchSignalRead,
  ReviewScriptResponse,
  StrategyRead,
  StrategyStatus,
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

export function listContentItems(creatorId: string) {
  return request<ContentItemRead[]>(`/creators/${creatorId}/content`);
}

export function createContentFromOpportunity(creatorId: string, opportunityId: string) {
  return request<ContentItemRead>(`/creators/${creatorId}/content/from-opportunity`, {
    method: "POST",
    body: JSON.stringify({ opportunity_id: opportunityId }),
  });
}

export function getContentDetail(creatorId: string, contentItemId: string) {
  return request<ContentDetailRead>(`/creators/${creatorId}/content/${contentItemId}`);
}

export function generateBrief(creatorId: string, contentItemId: string) {
  return request<GenerateBriefResponse>(`/creators/${creatorId}/content/${contentItemId}/generate-brief`, {
    method: "POST",
  });
}

export function generateScript(creatorId: string, contentItemId: string) {
  return request<GenerateScriptResponse>(`/creators/${creatorId}/content/${contentItemId}/generate-script`, {
    method: "POST",
  });
}

export function reviewScript(creatorId: string, contentItemId: string, scriptId: string) {
  return request<ReviewScriptResponse>(`/creators/${creatorId}/content/${contentItemId}/review`, {
    method: "POST",
    body: JSON.stringify({ script_id: scriptId }),
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

export function generateStrategy(creatorId: string) {
  return request<GenerateStrategyResponse>(`/creators/${creatorId}/strategy/generate`, { method: "POST" });
}

export function listStrategies(creatorId: string) {
  return request<StrategyRead[]>(`/creators/${creatorId}/strategy`);
}

export function updateStrategyStatus(creatorId: string, strategyId: string, status: StrategyStatus) {
  return request<StrategyRead>(`/creators/${creatorId}/strategy/${strategyId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function createAudienceSignal(creatorId: string, payload: AudienceSignalCreate) {
  return request<AudienceSignalRead>(`/creators/${creatorId}/audience-signals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAudienceSignals(creatorId: string) {
  return request<AudienceSignalRead[]>(`/creators/${creatorId}/audience-signals`);
}

export function analyzeAudience(creatorId: string) {
  return request<AnalyzeAudienceResponse>(`/creators/${creatorId}/audience/analyze`, { method: "POST" });
}
