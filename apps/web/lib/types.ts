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

export interface StrategicLearningSummary {
  id: string;
  statement: string;
  scope: string;
  confidence: number;
}

export interface CreatorStateSnapshot {
  creator: CreatorRead;
  positioning: CreatorProfileRead | null;
  voice: VoiceProfileRead | null;
  audience: AudienceProfileRead | null;
  active_goals: CreatorGoalRead[];
  recent_content: RecentContentSummary[];
  content_pillars: ContentPillarSummary[];
  audience_segments: AudienceSegmentRead[];
  top_performing_content: unknown[];
  recent_failures: unknown[];
  current_research_signals: ResearchSignalSummary[];
  active_experiments: unknown[];
  strategic_learnings: StrategicLearningSummary[];
  commercial_profile: CommercialProfileRead | null;
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

export interface ContentItemRead {
  id: string;
  title: string | null;
  platform: string | null;
  format: string | null;
  topic: string | null;
  status: string;
  source_type: string;
  transcript: string | null;
  opportunity_id: string | null;
  pillar_id: string | null;
  created_at: string;
}

export interface ContentBriefRead {
  id: string;
  objective: string | null;
  core_insight: string | null;
  angle: string | null;
  hook_type: string | null;
  hook: string | null;
  narrative_structure: Record<string, string> | null;
  key_points: string[] | null;
  examples: string[] | null;
  broll_suggestions: string[] | null;
  on_screen_text: string[] | null;
  pacing: string | null;
  cta: string | null;
  caption_concept: string | null;
  cover_concept: string | null;
  repurposing_opportunities: string[] | null;
  evidence_ids: string[] | null;
  risk_notes: string | null;
}

export interface CriticIssue {
  type: string;
  severity: "low" | "medium" | "high";
  location: string;
  suggestion: string;
}

export interface ScriptRead {
  id: string;
  brief_id: string | null;
  version_number: number;
  platform: string | null;
  body: string;
  hook_variants: string[] | null;
  status: "draft" | "critiqued" | "rewritten" | "final";
  critic_score: number | null;
  critic_issues: CriticIssue[] | null;
}

export interface ContentDetailRead {
  item: ContentItemRead;
  brief: ContentBriefRead | null;
  scripts: ScriptRead[];
}

export interface GenerateBriefResponse {
  brief: ContentBriefRead | null;
  warnings: string[];
}

export interface GenerateScriptResponse {
  script: ScriptRead | null;
  warnings: string[];
}

export interface ReviewScriptResponse {
  reviewed: ScriptRead | null;
  rewrite: ScriptRead | null;
  warnings: string[];
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

export interface AudienceSegmentRead {
  id: string;
  name: string;
  problems: string[] | null;
  desires: string[] | null;
  objections: string[] | null;
  questions: string[] | null;
  fears: string[] | null;
  aspirations: string[] | null;
  language: string[] | null;
  knowledge_level: string | null;
  confidence: number;
  sample_size: number | null;
}

export interface AudienceSignalCreate {
  text: string;
  source_platform?: string;
}

export interface AudienceSignalRead {
  id: string;
  text: string;
  source_platform: string | null;
  created_at: string;
}

export interface AnalyzeAudienceResponse {
  audience: AudienceProfileRead | null;
  segments: AudienceSegmentRead[];
  warnings: string[];
}

export interface CalendarEventRead {
  id: string;
  content_item_id: string | null;
  content_title: string | null;
  content_status: string | null;
  content_format: string | null;
  scheduled_at: string | null;
  platform: string | null;
  status: "planned" | "scheduled" | "published" | "missed";
}

export interface ScheduleContentRequest {
  scheduled_at: string;
  platform?: string;
}

export interface ScheduleContentResponse {
  item: ContentItemRead;
  event: CalendarEventRead;
}

export interface PublishContentRequest {
  url?: string;
  external_id?: string;
}

export interface PublishContentResponse {
  item: ContentItemRead;
  published_at: string;
  url: string | null;
}

export interface BottleneckRead {
  type: string;
  message: string;
  evidence: Record<string, number>;
}

export interface CapacityRead {
  items_per_week: number | null;
}

export interface PerformanceSnapshotCreate {
  views?: number;
  watch_time?: number;
  avg_view_duration?: number;
  retention?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  saves?: number;
  followers_gained?: number;
  profile_visits?: number;
  captured_at?: string;
}

export interface PerformanceSnapshotRead {
  id: string;
  content_item_id: string;
  views: number | null;
  watch_time: number | null;
  avg_view_duration: number | null;
  retention: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  followers_gained: number | null;
  profile_visits: number | null;
  baseline_comparison: Record<string, unknown> | null;
  captured_at: string;
}

export interface AssociatedFactor {
  factor: string;
  confidence: string;
  note: string;
}

export interface DiagnosisRead {
  summary: string;
  associated_factors: AssociatedFactor[];
  next_test: string | null;
  confidence: string;
}

export interface DiagnoseResponse {
  snapshot: PerformanceSnapshotRead;
  diagnosis: DiagnosisRead | null;
  warnings: string[];
}

export interface PerformanceOverviewItem {
  content_item_id: string;
  title: string | null;
  topic: string | null;
  format: string | null;
  platform: string | null;
  latest_snapshot: PerformanceSnapshotRead | null;
}

export interface CommercialProfileRead {
  id: string;
  version: number;
  ideal_sponsor_categories: string[] | null;
  prohibited_categories: string[] | null;
  target_geographies: string[] | null;
  preferred_deal_formats: string[] | null;
  minimum_conditions: string | null;
  exclusivity_constraints: string | null;
  usage_rights_preferences: string | null;
  sponsorship_goals: string | null;
  revenue_goal: string | null;
  brands_to_avoid: string[] | null;
  confidence: number;
}

export interface CommercialProfileUpdate {
  ideal_sponsor_categories?: string[];
  prohibited_categories?: string[];
  target_geographies?: string[];
  preferred_deal_formats?: string[];
  minimum_conditions?: string;
  exclusivity_constraints?: string;
  usage_rights_preferences?: string;
  sponsorship_goals?: string;
  revenue_goal?: string;
  brands_to_avoid?: string[];
}

export interface BrandCreate {
  name: string;
  website?: string;
  category?: string;
  subcategory?: string;
  description?: string;
  geography?: string;
  target_customer?: string[];
  products?: string[];
  positioning?: string;
  competitors?: string[];
}

export interface BrandRead {
  id: string;
  name: string;
  website: string | null;
  category: string | null;
  subcategory: string | null;
  description: string | null;
  geography: string | null;
  target_customer: string[] | null;
  products: string[] | null;
  positioning: string | null;
  competitors: string[] | null;
  source: string;
  confidence: number;
  status: string;
  created_at: string;
}

export interface BrandContactCreate {
  name?: string;
  role?: string;
  department?: string;
  email?: string;
  profile_url?: string;
  source?: string;
  verification_state?: string;
}

export interface BrandContactRead {
  id: string;
  brand_id: string;
  name: string | null;
  role: string | null;
  department: string | null;
  email: string | null;
  profile_url: string | null;
  source: string | null;
  verification_state: string;
  confidence: number;
  last_verified_at: string | null;
}

export interface BrandSignalCreate {
  signal_type?: string;
  summary: string;
  source_url?: string;
  source_note?: string;
  observed_at?: string;
  evidence_quality?: string;
}

export interface BrandSignalRead {
  id: string;
  brand_id: string | null;
  signal_type: string | null;
  summary: string;
  source_url: string | null;
  source_note: string | null;
  observed_at: string | null;
  retrieved_at: string;
  evidence_quality: string | null;
}

export interface BrandOpportunityRead {
  id: string;
  brand_id: string;
  score: number | null;
  score_components: Record<string, number> | null;
  reasons: string | null;
  evidence_signal_ids: string[];
  suggested_contact_roles: string[];
  confidence: number;
  status: string;
  prohibited_conflict: boolean;
}

export interface ScoreBrandOpportunityResponse {
  opportunity: BrandOpportunityRead | null;
  warnings: string[];
}

export interface CampaignBriefRead {
  id: string;
  brand_opportunity_id: string;
  objective_hypothesis: string | null;
  campaign_concept: string | null;
  content_format: string | null;
  why_this_brand: string | null;
  why_now: string | null;
  suggested_cta: string | null;
  suggested_deliverables: string[] | null;
  pitch_angle: string | null;
  personalization_facts: string[] | null;
  evidence_signal_ids: string[];
  confidence: number;
}

export interface GenerateCampaignBriefResponse {
  brief: CampaignBriefRead | null;
  warnings: string[];
}

export interface BrandRadarItem {
  brand: BrandRead;
  opportunity: BrandOpportunityRead;
}

export interface ExtractedReplyData {
  sentiment: "interested" | "neutral" | "declining";
  summary: string;
  budget_mentioned: string | null;
  timeline_mentioned: string | null;
  deliverables_mentioned: string[];
  next_steps_from_brand: string | null;
  open_questions: string[];
  flags: string[];
}

export interface OutreachMessageRead {
  id: string;
  thread_id: string;
  direction: "outbound" | "inbound";
  kind: "initial_pitch" | "follow_up" | "brand_reply";
  subject: string | null;
  body: string;
  status: "draft" | "approved" | "sent" | null;
  sent_at: string | null;
  extracted_data: ExtractedReplyData | null;
  created_at: string;
}

export interface OutreachThreadRead {
  id: string;
  brand_opportunity_id: string;
  contact_id: string | null;
  campaign_brief_id: string | null;
  status: string;
  outcome: string | null;
  creator_decision: string | null;
  creator_decision_note: string | null;
  decided_at: string | null;
  deal_value: number | null;
  created_at: string;
}

export interface OutreachThreadDetail {
  thread: OutreachThreadRead;
  brand: BrandRead;
  messages: OutreachMessageRead[];
}

export interface OutreachPipelineItem {
  thread: OutreachThreadRead;
  brand: BrandRead;
}

export interface CreateOutreachThreadResponse {
  thread: OutreachThreadRead | null;
  message: OutreachMessageRead | null;
  warnings: string[];
}

export interface DraftFollowUpResponse {
  message: OutreachMessageRead | null;
  warnings: string[];
}

export interface RecordBrandReplyResponse {
  message: OutreachMessageRead;
  warnings: string[];
}

export type CreatorDecision = "accept" | "negotiate" | "decline" | "need_more_info" | "archive";

export interface LearningRead {
  id: string;
  statement: string;
  category: string | null;
  evidence_ids: string[];
  confidence: number;
  first_observed_at: string;
  last_validated_at: string | null;
  status: string;
  scope: string;
}
