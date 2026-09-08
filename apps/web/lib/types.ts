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

export interface CreatorStateSnapshot {
  creator: CreatorRead;
  positioning: CreatorProfileRead | null;
  voice: VoiceProfileRead | null;
  audience: AudienceProfileRead | null;
  active_goals: CreatorGoalRead[];
  recent_content: RecentContentSummary[];
  top_performing_content: unknown[];
  recent_failures: unknown[];
  current_research_signals: unknown[];
  active_experiments: unknown[];
  strategic_learnings: unknown[];
}

export interface ContentItemCreate {
  title: string;
  platform?: string;
  format?: string;
  topic?: string;
  transcript?: string;
}
