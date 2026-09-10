import type {
  AnalyzeAudienceResponse,
  AnalyzeCreatorResponse,
  AudienceSignalCreate,
  AudienceSignalRead,
  BottleneckRead,
  BrandContactCreate,
  BrandContactRead,
  BrandCreate,
  BrandRead,
  BrandSignalCreate,
  BrandSignalRead,
  CalendarEventRead,
  CapacityRead,
  CommercialProfileRead,
  CommercialProfileUpdate,
  ContentDetailRead,
  ContentItemCreate,
  ContentItemRead,
  CreatorCreateResponse,
  CreatorRead,
  CreatorStateSnapshot,
  DiagnoseResponse,
  GenerateBriefResponse,
  GenerateOpportunitiesResponse,
  GenerateScriptResponse,
  GenerateStrategyResponse,
  LearningRead,
  OpportunityRead,
  OpportunityStatus,
  PerformanceOverviewItem,
  PerformanceSnapshotCreate,
  PerformanceSnapshotRead,
  PublishContentRequest,
  PublishContentResponse,
  ResearchSignalCreate,
  ResearchSignalRead,
  ReviewScriptResponse,
  ScheduleContentRequest,
  ScheduleContentResponse,
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

export function markContentRecorded(creatorId: string, contentItemId: string) {
  return request<ContentItemRead>(`/creators/${creatorId}/content/${contentItemId}/mark-recorded`, {
    method: "POST",
  });
}

export function markContentEditing(creatorId: string, contentItemId: string) {
  return request<ContentItemRead>(`/creators/${creatorId}/content/${contentItemId}/mark-editing`, {
    method: "POST",
  });
}

export function scheduleContent(creatorId: string, contentItemId: string, payload: ScheduleContentRequest) {
  return request<ScheduleContentResponse>(`/creators/${creatorId}/content/${contentItemId}/schedule`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function publishContent(creatorId: string, contentItemId: string, payload: PublishContentRequest) {
  return request<PublishContentResponse>(`/creators/${creatorId}/content/${contentItemId}/publish`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listCalendarEvents(creatorId: string) {
  return request<CalendarEventRead[]>(`/creators/${creatorId}/calendar`);
}

export function listBottlenecks(creatorId: string) {
  return request<BottleneckRead[]>(`/creators/${creatorId}/calendar/bottlenecks`);
}

export function getCapacity(creatorId: string) {
  return request<CapacityRead>(`/creators/${creatorId}/capacity`);
}

export function setCapacity(creatorId: string, itemsPerWeek: number) {
  return request<CapacityRead>(`/creators/${creatorId}/capacity`, {
    method: "PUT",
    body: JSON.stringify({ items_per_week: itemsPerWeek }),
  });
}

export function ingestPerformance(creatorId: string, contentItemId: string, payload: PerformanceSnapshotCreate) {
  return request<PerformanceSnapshotRead>(`/creators/${creatorId}/content/${contentItemId}/performance`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPerformance(creatorId: string, contentItemId: string) {
  return request<PerformanceSnapshotRead[]>(`/creators/${creatorId}/content/${contentItemId}/performance`);
}

export function diagnosePerformance(creatorId: string, contentItemId: string) {
  return request<DiagnoseResponse>(`/creators/${creatorId}/content/${contentItemId}/performance/diagnose`, {
    method: "POST",
  });
}

export function getPerformanceOverview(creatorId: string) {
  return request<PerformanceOverviewItem[]>(`/creators/${creatorId}/performance/overview`);
}

export function getCommercialProfile(creatorId: string) {
  return request<CommercialProfileRead | null>(`/creators/${creatorId}/commercial-profile`);
}

export function updateCommercialProfile(creatorId: string, payload: CommercialProfileUpdate) {
  return request<CommercialProfileRead>(`/creators/${creatorId}/commercial-profile`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function createBrand(creatorId: string, payload: BrandCreate) {
  return request<BrandRead>(`/creators/${creatorId}/brands`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listBrands(creatorId: string) {
  return request<BrandRead[]>(`/creators/${creatorId}/brands`);
}

export function getBrand(creatorId: string, brandId: string) {
  return request<BrandRead>(`/creators/${creatorId}/brands/${brandId}`);
}

export function addBrandContact(creatorId: string, brandId: string, payload: BrandContactCreate) {
  return request<BrandContactRead>(`/creators/${creatorId}/brands/${brandId}/contacts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listBrandContacts(creatorId: string, brandId: string) {
  return request<BrandContactRead[]>(`/creators/${creatorId}/brands/${brandId}/contacts`);
}

export function addBrandSignal(creatorId: string, brandId: string, payload: BrandSignalCreate) {
  return request<BrandSignalRead>(`/creators/${creatorId}/brands/${brandId}/signals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listBrandSignals(creatorId: string, brandId: string) {
  return request<BrandSignalRead[]>(`/creators/${creatorId}/brands/${brandId}/signals`);
}

export function getLearnings(creatorId: string) {
  return request<LearningRead[]>(`/creators/${creatorId}/learnings`);
}

export function syncLearnings(creatorId: string) {
  return request<LearningRead[]>(`/creators/${creatorId}/learnings/sync`, { method: "POST" });
}

export function retractLearning(creatorId: string, learningId: string) {
  return request<LearningRead>(`/creators/${creatorId}/learnings/${learningId}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "retracted" }),
  });
}
