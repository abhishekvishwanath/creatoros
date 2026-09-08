export interface CreatorRead {
  id: string;
  name: string;
  niche: string | null;
  sub_niche: string | null;
  geography: string | null;
  languages: string[] | null;
  business_model: string | null;
  monetization_model: string | null;
  onboarding_status: string;
  created_at: string;
  updated_at: string;
}

export interface CreatorCreateResponse extends CreatorRead {
  user_id: string;
}

export interface CreatorProfileRead {
  bio: string | null;
  expertise: string[] | null;
  positioning_statement: string | null;
  prohibited_topics: string[] | null;
  avoided_claims: string[] | null;
  rejected_tones: string[] | null;
  disclosure_requirements: string[] | null;
  confidence: number;
}

export interface VoiceProfileRead {
  tone: string | null;
  vocabulary: string[] | null;
  sentence_style: string | null;
  pacing: string | null;
  personality: string | null;
  humor_level: string | null;
  controversy_tolerance: string | null;
  storytelling_style: string | null;
  opinion_style: string | null;
  signature_phrases: string[] | null;
  cta_style: string | null;
  confidence: number;
}

export interface AudienceProfileRead {
  geography: string[] | null;
  demographics: Record<string, unknown> | null;
  psychographics: Record<string, unknown> | null;
  knowledge_level: string | null;
  purchase_intent: string | null;
  preferred_language: string | null;
  confidence: number;
}

export interface CreatorGoalRead {
  id: string;
  goal_type: string;
  description: string | null;
  target_metric: string | null;
  target_value: number | null;
  priority: number;
  status: string;
}

export interface RecentContentSummary {
  id: string;
  title: string | null;
  platform: string | null;
  format: string | null;
  topic: string | null;
  has_transcript: boolean;
}

export interface ContentPillarSummary {
  id: string;
  name: string;
  description: string | null;
}

export interface ResearchSignalSummary {
  id: string;
  topic: string | null;
  subtopic: string | null;
  format: string | null;
}

export interface CreatorStateSnapshot {
  creator: CreatorRead;
  positioning: CreatorProfileRead | null;
  voice: VoiceProfileRead | null;
  audience: AudienceProfileRead | null;
  active_goals: CreatorGoalRead[];
  recent_content: RecentContentSummary[];
  content_pillars: ContentPillarSummary[];
  top_performing_content: unknown[];
  recent_failures: unknown[];
  current_research_signals: ResearchSignalSummary[];
  active_experiments: unknown[];
  strategic_learnings: unknown[];
}

export interface AnalyzeCreatorResponse {
  state: CreatorStateSnapshot;
  warnings: string[];
}

export interface ContentItemCreate {
  title: string;
  platform?: string;
  format?: string;
  topic?: string;
  transcript?: string;
}

export interface ResearchSignalCreate {
  topic: string;
  subtopic?: string;
  format?: string;
  summary: string;
  platform?: string;
  source_url?: string;
  source_title?: string;
}

export interface ResearchSignalRead {
  id: string;
  topic: string | null;
  subtopic: string | null;
  format: string | null;
  content_features: { summary?: string } | null;
  evidence_quality: string | null;
  source_id: string | null;
  created_at: string;
}

export interface OpportunityEvidenceRead {
  research_signal_id: string | null;
  content_item_id: string | null;
  note: string | null;
}

export interface OpportunityRead {
  id: string;
  topic: string | null;
  subtopic: string | null;
  angle: string | null;
  format: string | null;
  content_pillar_id: string | null;
  score: number | null;
  score_components: Record<string, number> | null;
  competition_level: string | null;
  saturation_estimate: string | null;
  production_complexity: string | null;
  recommended_time_window: string | null;
  confidence: number | null;
  status: "pending" | "approved" | "rejected" | "saved_for_later" | "used";
  created_at: string;
  evidence: OpportunityEvidenceRead[];
}

export interface GenerateOpportunitiesResponse {
  opportunities: OpportunityRead[];
  warnings: string[];
}

export type OpportunityStatus = "approved" | "rejected" | "saved_for_later" | "used";

export interface StrategyItemRead {
  id: string;
  opportunity_id: string | null;
  opportunity_topic: string | null;
  day_of_week: number | null;
  portfolio_role: string | null;
  status: string;
}

export interface StrategyRead {
  id: string;
  period_start: string | null;
  period_end: string | null;
  summary: string | null;
  status: "draft" | "active" | "completed";
  confidence: number | null;
  created_at: string;
  items: StrategyItemRead[];
}

export interface GenerateStrategyResponse {
  strategy: StrategyRead | null;
  warnings: string[];
}

export type StrategyStatus = "draft" | "active" | "completed";
