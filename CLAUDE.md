# CLAUDE.md — Creator Intelligence OS

## 0. DOCUMENT PURPOSE

This file is the primary product, engineering, architecture, agent-behavior, and implementation context for Claude Code working on the Creator Intelligence OS.

Read this file before making architectural, product, workflow, database, agent, UI, or infrastructure changes.

This product is NOT simply an AI script generator, social scheduler, trend dashboard, or content calendar.

The product is an **AI Content + Commercial Intelligence Operating System for growing creators**. Sections 1–64 below define the Content Intelligence loop (the original core); [Part II](#part-ii--commercial-intelligence--brand-outbound-layer) at the end of this file defines the Commercial Intelligence loop (brand/sponsorship discovery and outbound) that runs alongside it, sharing the same Creator Brain, Learning Engine, and Creator State. Both loops are the product — read Part II before touching anything commercial-layer related (brands, contacts, outreach, campaign briefs).

The system continuously learns:

- who the creator is
- how the creator communicates
- who the creator serves
- what content the creator has already produced
- what has historically worked or failed
- what competitors are doing
- what audiences are discussing
- what topics are gaining momentum
- what opportunities fit the creator specifically
- what the creator should create next
- what happened after publication
- what the system learned from that result

The fundamental loop is:

**UNDERSTAND → RESEARCH → DECIDE → CREATE → PUBLISH → MEASURE → LEARN → REPEAT**

The goal is to build the engine and test it against the **real daily routine of 5 growing creators**, using their actual content histories, content production, publishing, and performance feedback to determine whether the system genuinely saves time and improves content decisions and output.

---

# 1. PRODUCT NORTH STAR

## 1.1 Core product promise

> The creator should not have to spend their limited creative energy figuring out what to create, why to create it, how to structure it, and what to learn from the result.
>
> The system should continuously do the intelligence and operational work around the creator's creativity while leaving the creator in control of their voice, taste, experiences, and final creative judgment.

## 1.2 Product category

Position as:

- AI Content Strategist
- Creator Intelligence OS
- AI Content Department
- Intelligent Content Growth Engine

Do NOT position primarily as:

- AI content generator
- AI script writer
- social media scheduler
- competitor research tool
- analytics dashboard
- generic content calendar

Those are supporting capabilities, not the product identity.

## 1.3 Product thesis

A growing solo creator is effectively doing the work of a small media team:

1. Strategist — what should I make?
2. Researcher — what matters right now?
3. Audience analyst — what does my audience care about?
4. Competitor analyst — what is working elsewhere?
5. Copywriter — how do I structure the message?
6. Creative director — what angle/format/visual treatment should it have?
7. Producer — how do I actually execute it?
8. Social manager — when/where do I publish?
9. Analyst — why did it perform or fail?
10. Growth strategist — what should I do differently next time?

The product exists to automate or accelerate the repetitive intelligence and operations around those jobs.

---

# 2. TARGET CUSTOMER

## 2.1 Primary ICP

Growing creators who:

- publish consistently
- have an established niche or emerging specialization
- are serious about growth
- already have enough content history for meaningful analysis
- are monetizing or intend to monetize
- still perform most of their strategy/content work themselves
- do not yet have a full content team
- feel overloaded by research, planning, writing, repurposing, scheduling, and analytics
- value their unique voice and want to retain creative control

The ideal early customer is not necessarily the creator with the largest follower count.

The ideal customer is the creator for whom **strategic bandwidth is already a bottleneck**.

## 2.2 Strong creator profiles

Examples:

- education creators
- AI/technology creators
- career creators
- finance/business creators
- coding/programming creators
- fitness creators
- beauty/fashion creators
- lifestyle creators
- travel creators
- expert-led creators
- consultants/coaches/founders building personal brands
- creators selling services, courses, communities, newsletters, products, or sponsorship inventory

## 2.3 Weak initial customers

Avoid optimizing for:

- people who rarely publish
- accounts with almost no historical content
- creators without any clear audience or topic
- users seeking only captions or one-off scripts
- users who do not care about performance
- users who want fully automated faceless content with no creator involvement
- creators who do not implement recommendations

The value of the system compounds with historical content, audience feedback, creator memory, and performance data.

---

# 3. PRODUCT PRINCIPLES — NON-NEGOTIABLE

## 3.1 Creator-first

The creator is the central entity in the system.

Every major object must ultimately be traceable to a `creator_id`.

## 3.2 Creator remains in control

AI should support and elevate creative judgment, not erase it.

Human approval should normally be required before:

- final publishing
- major strategy shifts
- externally visible communications
- deleting creator content/data
- actions that materially affect the creator's brand

## 3.3 Intelligence over generation

Do not optimize for how many AI outputs the product can generate.

Optimize for:

- better decisions
- better opportunity selection
- faster production
- better content consistency
- better learning from performance
- less repetitive work

## 3.4 Evidence over vibes

Whenever the product makes a strategic recommendation, it should be possible to answer:

> Why did the system recommend this?

Recommendations should be traceable to some combination of:

- creator history
- audience signals
- performance evidence
- research signals
- competitor patterns
- current topic momentum
- creator goals

Never present an unsupported guess as established truth.

## 3.5 Do not blindly optimize for virality

A high-view post can still be strategically bad if it attracts the wrong audience or weakens positioning.

Opportunity scoring should consider:

**Creator Goal × Audience Fit × Creator Fit × Demand × Novelty × Evidence − Competition − Saturation − Production Complexity**

## 3.6 Do not copy creators

The research engine should identify patterns, structures, audience needs, topics, and opportunities.

It must not intentionally reproduce another creator's scripts, captions, distinctive creative expression, or protected content.

Transform insights into the target creator's original perspective and voice.

## 3.7 One source of truth

Do not allow different agents to maintain independent versions of creator identity or creator strategy.

The persistent entity/state layer is authoritative.

## 3.8 Agents are replaceable; creator data is not

Model providers and individual agent implementations can change.

Creator history, content, audience intelligence, performance, experiments, and learnings must remain model-independent.

---

# 4. THE CORE CONCEPT: SINGLE ENTITY + SHARED STATE

## 4.1 Creator is the top-level entity

Every creator receives one immutable identifier:

```text
creator_id = cr_<stable-unique-id>
```

All related data references this ID.

## 4.2 Do NOT create a spaghetti network of agents

Do not design:

```text
Research Agent → Strategy Agent → Script Agent → Critic → Analytics Agent → ...
```

as direct hard-coded dependencies.

Instead:

```text
                     CREATOR ENTITY
                          |
                    CREATOR STATE
                          |
       +------------------+------------------+
       |                  |                  |
    Agents             Tools             Memory
       |                  |                  |
       +------------------+------------------+
                          |
                    Event / State Layer
                          |
                   Creator State updated
```

All intelligent systems read from and write back to shared persistent state through validated interfaces.

## 4.3 Entity graph

The system should track multiple entity types:

```text
Creator
Audience Segment
Topic
Subtopic
Content Piece
Content Version
Hook
Format
Content Pillar
Competitor
Platform
Research Signal
Opportunity
Strategy
Experiment
Performance Event
Strategic Learning
Calendar Event
Goal
Source / Evidence
Agent Run
```

Important relationships include:

```text
Creator
 ├── owns → Social Account
 ├── targets → Audience Segment
 ├── discusses → Topic
 ├── creates → Content
 ├── competes with → Competitor
 └── pursues → Goal

Content
 ├── uses → Hook
 ├── belongs to → Topic
 ├── belongs to → Content Pillar
 ├── published on → Platform
 ├── targets → Audience Segment
 ├── derived from → Opportunity
 ├── participates in → Experiment
 └── produces → Performance

Performance
 └── produces → Learning

Learning
 └── updates → Creator State
```

This is the foundation of the long-term intelligence layer.

---

# 5. CREATOR STATE

## 5.1 Creator State is NOT one giant context file

A `personal_context.md` file can be generated for readability/export/onboarding, but it must not be the system's only source of truth.

Persist structured data in PostgreSQL.

Persist semantic material in pgvector.

Persist media in object storage.

## 5.2 Creator state domains

The state should include:

```text
Identity
Positioning
Audience
Voice
Content Pillars
Content Library
Competitors
Goals
Monetization
Research Signals
Opportunities
Strategies
Calendar
Performance
Experiments
Strategic Learnings
Creator Preferences
Operational Capacity
```

## 5.3 Historical + current + experimental state

Never treat all knowledge as equally current.

Every strategic knowledge item should be distinguishable as one of:

- historical pattern
- current signal
- active experiment
- unresolved/low-confidence hypothesis
- explicit creator preference

This prevents one viral post from becoming a permanent false rule.

---

# 6. MEMORY ARCHITECTURE

Use multiple memory layers.

## 6.1 Relational source of truth

PostgreSQL stores:

- creators
- accounts
- profiles
- content
- content versions
- metrics
- opportunities
- strategies
- experiments
- calendar
- learnings
- agent runs
- relationships
- statuses

## 6.2 Semantic memory

pgvector stores/retrieves semantically relevant content such as:

- old scripts
- creator statements
- audience comments
- research snippets
- content examples
- strategic learnings
- relevant source passages

## 6.3 Object storage

S3-compatible storage / Cloudflare R2 stores:

- videos
- images
- audio
- generated files
- transcripts
- documents
- thumbnails

## 6.4 Memory hierarchy

Conceptually:

```text
Short-term memory
↓ current content task

Episodic memory
↓ what happened in previous tasks

Semantic memory
↓ what we know about the creator/audience/topics

Performance memory
↓ what worked and failed

Strategic memory
↓ current strategy and hypotheses

Research memory
↓ recent external signals

Content memory
↓ all previously created content
```

---

# 7. CREATOR DNA

Creator DNA is the structured model of the creator.

## 7.1 Identity

Track:

- name
- bio
- niche
- sub-niche
- expertise
- positioning
- geography
- language(s)
- business model
- monetization model

## 7.2 Audience

Track:

- geography
- demographics
- psychographics
- problems
- desires
- aspirations
- objections
- knowledge level
- purchase intent
- preferred language
- recurring questions

## 7.3 Brand and voice

Track:

- tone
- vocabulary
- sentence style
- pacing
- personality
- humor level
- controversy tolerance
- storytelling style
- opinion style
- signature phrases/patterns
- preferred CTA style

## 7.4 Content system

Track:

- content pillars
- recurring topics
- format preferences
- high-performing hooks
- weak hooks
- storytelling patterns
- average duration
- visual patterns
- CTA patterns
- publishing cadence

## 7.5 Creator boundaries

Track:

- prohibited topics
- claims creator avoids
- tone creator rejects
- brand safety constraints
- disclosure requirements
- topics that must remain personal/human

---

# 8. AGENT SERVICE

## 8.1 Definition

The Agent Service is the backend subsystem responsible for executing, coordinating, observing, and governing all AI agents.

It is the layer between the application/backend and the model/tool ecosystem.

Conceptually:

```text
FastAPI
   |
   v
Agent Service
   |
   +-- Orchestrator
   +-- Context Builder
   +-- Model Router
   +-- Agent Runtime
   +-- Tool Manager
   +-- Memory Writer
   +-- Output Validator
   +-- Observability
   |
   v
Claude / other approved models
```

## 8.2 Agent Service responsibilities

It handles:

- agent registry
- model routing
- context assembly
- tool permissions
- prompt execution
- structured output validation
- retries
- timeouts
- cost tracking
- logging
- agent run IDs
- event emission
- state transition requests
- error handling
- auditability

## 8.3 Agents should NOT directly perform arbitrary DB mutations

Prefer:

```text
Agent → structured command/event → validator/state service → DB
```

rather than:

```text
Agent → unrestricted SQL
```

Example event:

```json
{
  "event": "learning.created",
  "creator_id": "cr_123",
  "data": {
    "insight": "Practical workflow content outperforms generic tool-list content",
    "confidence": 0.86,
    "evidence_ids": ["cnt_882", "cnt_911", "cnt_932"]
  }
}
```

---

# 9. ORCHESTRATOR

The Orchestrator answers:

> What should happen next?

It should determine:

- which agent runs
- which agent runs first
- what context is required
- what tools are available
- whether the task requires fresh research
- whether human approval is required
- what event/state transition follows success
- what happens on failure

The Orchestrator should not itself become a giant reasoning monolith.

It coordinates; specialized agents reason.

---

# 10. CONTEXT BUILDER

The Context Builder generates the right context for each agent.

Never dump the creator's entire database into every model call.

For each task, retrieve only relevant context.

Example for Script Agent:

```text
Creator voice
+
Audience profile
+
Approved opportunity
+
Current strategy
+
3-5 relevant successful scripts
+
Relevant past failures
+
Required source/evidence
+
Creator content constraints
```

Example for Performance Agent:

```text
Current metrics
+
Historical creator baseline
+
Comparable prior posts
+
Experiment context
+
Original strategy
+
Platform context
```

Context must be:

- task-specific
- traceable
- bounded
- versioned where necessary
- cost-aware

---

# 11. AGENT ROSTER

Start with a small number of strong agents. Do not create an agent for every tiny operation.

## 11.1 Creator Intelligence Agent

Responsibilities:

- build/update Creator DNA
- analyze historical content
- infer voice and positioning
- identify content pillars
- maintain creator identity
- identify gaps in known creator information

Inputs:

- connected account data
- historical content
- creator questionnaire
- uploaded materials
- performance history

Outputs:

- structured Creator DNA updates
- confidence values
- evidence references

---

## 11.2 Audience Intelligence Agent

Responsibilities:

- analyze audience language
- classify audience problems
- identify desires
- identify objections
- identify questions
- build audience segments
- identify changes in audience interest

Potential inputs:

- comments
- available audience analytics
- Reddit discussions
- public conversations
- creator-provided audience information

---

## 11.3 Research Agent

Responsibilities:

- conduct cross-platform research
- identify relevant content
- retrieve source evidence
- normalize external signals
- identify competitor activity
- discover emerging narratives

Research should produce structured signals, not a raw link dump.

---

## 11.4 Trend Intelligence Agent

Responsibilities:

- identify topic momentum
- identify emerging narratives
- identify format trends
- estimate saturation
- differentiate temporary spikes from durable topics
- rank relevance to the creator

Never equate trendiness with relevance.

---

## 11.5 Strategy Agent

This is one of the highest-value agents.

Responsibilities:

- select opportunities
- rank them
- balance content portfolio
- align content with creator goals
- determine what should be created next
- explain why
- create weekly strategy

It should consider:

```text
Creator DNA
Audience
Performance History
Current Research
Competitors
Content Calendar
Current Experiments
Creator Capacity
Business Goals
```

---

## 11.6 Content Architect Agent

Responsibilities:

- select content format
- choose angle
- define hook type
- structure narrative
- define payoff
- define CTA
- define visual/editorial direction
- produce a complete content brief

---

## 11.7 Script Agent

Responsibilities:

- write creator-specific scripts
- adapt scripts to platform-native formats
- maintain creator voice
- produce alternate hooks
- produce editable versions

The Script Agent must not invent facts merely to make a script sound authoritative.

---

## 11.8 Editorial Critic Agent

Use a writer → critic → rewriter loop.

The critic checks:

- creator voice
- hook strength
- specificity
- audience relevance
- structure
- pacing
- unnecessary fluff
- repetition
- CTA quality
- platform fit
- factual claims
- originality
- brand constraints

The first draft is not automatically final.

---

## 11.9 Repurposing Agent

Takes a primary source asset and creates platform-native derivatives.

Example:

```text
1 YouTube video
→ 3 Reels
→ 1 Carousel
→ 5 short X posts
→ 1 X thread
→ 1 LinkedIn post
→ Story sequence
→ Newsletter draft
```

Repurposing means adaptation, not mechanical summarization.

---

## 11.10 Performance Intelligence Agent

Responsibilities:

- ingest metrics
- compare against account baselines
- diagnose performance
- identify variables correlated with stronger/weaker results
- produce recommendations

Do not overclaim causal relationships when evidence is weak.

Use language such as:

- associated with
- correlated with
- appears to contribute
- hypothesis
- low confidence

when causality is not established.

---

## 11.11 Experimentation Agent

Responsibilities:

- formulate hypotheses
- define variables
- create tests
- track experiments
- evaluate results
- determine whether to retain/reject hypotheses

Example:

```text
Hypothesis:
Contrarian hooks improve early retention.

Test:
5 posts.

Result:
Median first-3-second retention +18%.

Confidence:
Medium.

Recommendation:
Use contrarian hooks more frequently for reach-oriented posts.
```

---

# 12. MODEL ROUTING

Do not hard-code one model throughout the codebase.

Use a model abstraction/router.

Conceptually:

```text
High-complexity strategic synthesis
→ strongest approved reasoning model

Standard reasoning / generation
→ strong balanced model

Bulk classification / extraction
→ fast economical model
```

The current model family and exact model names may change over time.

Model identity belongs in configuration, not business logic.

All model calls should log:

- model identifier
- agent
- task
- token/input usage where available
- output usage where available
- latency
- failure status
- estimated cost

---

# 13. EVENT-DRIVEN ARCHITECTURE

Use events to decouple components.

Examples:

```text
creator.connected
creator.profile.updated
content.ingested
content.analyzed
research.completed
opportunity.created
strategy.created
content.brief.created
script.created
script.reviewed
content.approved
content.published
performance.synced
performance.analyzed
experiment.created
learning.created
creator_state.updated
```

Agents react to events or are explicitly invoked by the Orchestrator.

Avoid deep direct agent dependencies.

---

# 14. DATA MODEL

Core PostgreSQL entities should include at minimum:

```text
users
creators
social_accounts
creator_profiles
voice_profiles
audience_profiles
audience_segments
creator_goals
content_pillars
content_items
content_versions
content_assets
content_embeddings
competitors
research_signals
research_sources
opportunities
opportunity_evidence
strategies
strategy_items
content_briefs
scripts
calendar_events
published_content
performance_metrics
performance_snapshots
experiments
experiment_results
strategic_learnings
creator_preferences
agent_runs
agent_messages
agent_tool_calls
state_snapshots
```

Most creator-scoped tables should include:

```text
creator_id
created_at
updated_at
```

Use foreign keys and constraints where appropriate.

---

# 15. VERSIONING

Do not overwrite important history.

Version:

- Creator DNA when materially changed
- voice profiles
- strategies
- briefs
- scripts
- learnings where a hypothesis evolves

Example:

```text
script_812_v1
script_812_v2
script_812_v3
```

The current version is a state, but previous versions remain inspectable.

---

# 16. SOURCE / EVIDENCE MODEL

Every external research signal should preserve provenance where possible:

```text
source_id
platform
url
source_title
publisher/creator
published_at
retrieved_at
source_type
evidence_quality
content_reference
```

Every strategic recommendation should be able to reference supporting evidence IDs.

This allows the UI to show:

> Why this recommendation?

with a traceable explanation.

---

# 17. RESEARCH ENGINE

## 17.1 Research inputs

Potential sources:

- Instagram professional account data available through supported APIs
- YouTube Data API
- YouTube Analytics API
- X API
- Reddit API where appropriate
- web search
- creator-provided content
- creator websites/newsletters
- connected analytics

Never assume an API gives access to everything on a platform.

Build around official supported capabilities and create compliant fallback/import mechanisms when needed.

## 17.2 Normalized research object

Normalize external content into a common structure similar to:

```json
{
  "platform": "youtube",
  "creator_or_source": "...",
  "topic": "AI productivity",
  "subtopic": "student workflows",
  "format": "short",
  "published_at": "...",
  "engagement": {},
  "content_features": {},
  "audience_signals": {},
  "hook_type": "contrarian",
  "topic_cluster": "AI productivity",
  "source_url": "...",
  "evidence_quality": "high"
}
```

## 17.3 Research should answer

Not:

> What are 50 things happening online?

But:

> What matters to this creator, this audience, this positioning, and this current goal?

---

# 18. CONTENT UNDERSTANDING PIPELINE

For creator videos, conceptually:

```text
Video
↓
Transcription
↓
Scene/frame analysis
↓
Topic detection
↓
Hook detection
↓
Narrative structure detection
↓
Voice analysis
↓
CTA detection
↓
Visual pattern extraction
↓
Performance join
↓
Creator memory
```

Analyze both semantic and creative characteristics where technically available.

---

# 19. AUDIENCE INTELLIGENCE

The system must understand audience needs, not only demographics.

Build an Audience Problem Graph:

```text
Audience
├── Problems
├── Desires
├── Questions
├── Objections
├── Fears
├── Aspirations
├── Language
├── Knowledge Level
└── Purchase Intent
```

Use comments and public discussions as qualitative signals.

Never treat a small sample as definitive audience truth.

Record confidence and sample size where possible.

---

# 20. OPPORTUNITY ENGINE

This is one of the most differentiated components.

Every candidate content opportunity should contain:

```text
opportunity_id
creator_id
topic
subtopic
angle
format
audience
content_pillar
strategic_goal
score
score_components
evidence_ids
competition_level
saturation_estimate
production_complexity
recommended_time_window
confidence
created_at
```

Suggested scoring dimensions:

- audience fit
- creator fit
- topic momentum
- evidence of demand
- novelty
- monetization relevance
- strategic relevance
- competition
- saturation
- production complexity

Do not reduce this to a single opaque number. Expose score components in the UI.

---

# 21. STRATEGY ENGINE

Content must be treated as a portfolio.

A balanced weekly plan can contain:

- reach content
- authority content
- relationship/community content
- story content
- conversion content
- experimental content

The Strategy Agent should consider the creator's current business objective.

Example:

```text
Monday
Reach — practical AI workflow Reel

Wednesday
Authority — deep educational carousel

Friday
Community — audience question/response

Saturday
Story — personal lesson

Sunday
Conversion — product/service-oriented post
```

Do not force fixed ratios on every creator. Use strategy as the default and allow adaptation based on evidence.

---

# 22. CONTENT BRIEF

Every approved idea should generate a structured brief.

Required fields:

```text
Objective
Audience
Pillar
Core Insight
Angle
Format
Hook Type
Hook
Narrative Structure
Key Points
Examples
B-roll / visual suggestions
On-screen text
Pacing
CTA
Caption concept
Cover/thumbnail concept
Repurposing opportunities
Evidence / source notes
Risk / fact-check notes
```

The brief should make execution significantly easier for the creator and/or editor.

---

# 23. SCRIPTING SYSTEM

Scripts should be platform-native.

## Short-form video

Potential structure:

```text
0–2 sec — hook
2–7 sec — problem/context
7–25 sec — insight
25–40 sec — proof/example
40–50 sec — payoff
50–55 sec — CTA
```

This is a guideline, not a rigid template.

## Long-form

```text
Cold open
Promise
Context
Problem
Mechanism
Examples
Escalation
Resolution
CTA
```

## X / text formats

Use native structures appropriate to the platform.

The Script Agent must optimize for clarity, originality, creator voice, audience value, and format suitability.

---

# 24. WRITER → CRITIC → REWRITER

For high-value content generation, the pipeline should be:

```text
Strategy
↓
Content Architect
↓
Script Writer
↓
Editorial Critic
↓
Rewrite
↓
Creator Review
```

Do not let the system assume its first generation is high quality.

Critic outputs should be structured and actionable.

Example:

```json
{
  "score": 82,
  "issues": [
    {
      "type": "weak_hook",
      "severity": "medium",
      "location": "opening",
      "suggestion": "Create a stronger tension gap."
    }
  ],
  "passed": false
}
```

---

# 25. REPURPOSING ENGINE

The product should treat every major source asset as a content tree.

Example:

```text
20-minute YouTube video
↓
├── Reel 1
├── Reel 2
├── Reel 3
├── Carousel
├── X post
├── X thread
├── LinkedIn post
├── Story sequence
└── Newsletter
```

Each derivative must:

- preserve source truth
- adapt to the target platform
- maintain creator voice
- avoid repetitive phrasing
- expose any important transformations

---

# 26. CALENDAR / CONTENT OPERATIONS

Each content item should move through a state machine:

```text
IDEA
→ APPROVED
→ BRIEFED
→ SCRIPTED
→ RECORDED
→ EDITING
→ REVIEW
→ SCHEDULED
→ PUBLISHED
→ ANALYZING
→ LEARNED
```

The system should identify operational bottlenecks.

Examples:

> 8 approved ideas but only 2 scripts.

> High production complexity exceeds creator's weekly capacity.

> Several sponsored commitments conflict with strategic content.

Capacity should be part of planning.

---

# 27. PERFORMANCE INTELLIGENCE

Pull available platform metrics where permitted.

Important dimensions can include:

- views/reach
- watch time
- average view duration
- retention
- likes
- comments
- shares
- saves
- followers/subscribers gained
- profile visits
- click-through metrics where available
- audience composition where available

Never assume metric availability is identical across platforms.

---

# 28. PERFORMANCE BASELINES

Performance must be interpreted against the creator's own baseline, not only absolute numbers.

Examples:

- median views of last 20 posts
- median retention for same format
- average shares by pillar
- average follows generated by reach content
- performance against similar-length videos

Use robust statistics where appropriate because creator performance is noisy.

Prefer medians/percentiles over relying only on averages.

---

# 29. PERFORMANCE DIAGNOSIS

A diagnosis should answer:

### What happened?

Example:

> This Reel achieved 2.1× the creator's 30-day median views.

### What appears associated with the result?

Examples:

- hook type
- topic
- story vs educational format
- duration
- pacing
- audience fit
- shareability

### What is the confidence?

Do not pretend correlation proves causation.

### What should we test next?

Turn insight into an experiment.

---

# 30. EXPERIMENTATION

Every important strategic hypothesis should eventually be testable.

Experiment object:

```text
experiment_id
creator_id
hypothesis
variable
control/reference
planned_test_set
start_date
end_date
status
results
confidence
conclusion
next_action
```

Example:

```text
Hypothesis:
Personal stories improve shares for educational content.

Test:
3 educational posts with personal story framing.

Compare:
3 comparable educational posts without story framing.

Result:
...
```

---

# 31. LEARNING ENGINE

The Learning Engine converts performance and experiment results into persistent creator-specific knowledge.

Learning should include:

```text
learning_id
creator_id
statement
category
evidence_ids
confidence
first_observed_at
last_validated_at
status
scope
```

Possible scopes:

- creator-wide
- platform-specific
- format-specific
- topic-specific
- audience-segment-specific
- temporary experiment

A learning must not be promoted to a creator-wide truth without adequate evidence.

---

# 32. CREATOR STATE SNAPSHOT

Before major agent executions, build a task-specific Creator State Snapshot.

Example:

```json
{
  "creator": {},
  "positioning": {},
  "audience": {},
  "voice": {},
  "active_goals": [],
  "recent_content": [],
  "top_performing_content": [],
  "recent_failures": [],
  "current_research_signals": [],
  "active_experiments": [],
  "strategic_learnings": []
}
```

This is the model's working context, not the database itself.

Snapshots should have a traceable ID for important runs.

---

# 33. FULL USER WORKFLOW

## Phase 1 — Onboarding

Creator connects supported accounts and provides:

- niche
- goals
- target audience
- monetization model
- desired positioning
- topics they want to own
- topics they avoid
- preferred content formats
- creators they admire

## Phase 2 — Creator Intelligence Build

System analyzes historical content and creates:

- Creator DNA
- voice profile
- audience profile
- content pillars
- initial performance patterns
- initial content memory

Creator reviews and approves/corrects it.

## Phase 3 — Continuous Research

System periodically ingests:

- competitor content
- audience conversations
- topic movement
- news
- platform signals
- industry developments

## Phase 4 — Strategy

Strategy Agent selects high-value opportunities.

## Phase 5 — Creator Approval

Creator can:

- approve
- reject
- modify
- ask why
- save for later

These actions should themselves become useful preference signals.

## Phase 6 — Creation

Approved opportunity becomes:

```text
Brief
→ Hooks
→ Script
→ Critique
→ Rewrite
→ Final creator edit
```

## Phase 7 — Production

System can supply:

- shot list
- B-roll list
- on-screen text
- edit instructions
- cover guidance
- caption

## Phase 8 — Repurposing

Primary content becomes platform-native derivatives.

## Phase 9 — Scheduling / Publishing

Creator approves and schedules/publishes through supported integrations.

Publishing must not be mandatory for the value proposition.

## Phase 10 — Performance

Metrics synchronize.

## Phase 11 — Learning

Performance Agent → diagnosis → experiments → learnings → Creator State update.

---

# 34. SOFTWARE ARCHITECTURE

Recommended initial architecture:

```text
                         NEXT.JS
                            |
                            v
                         FASTAPI
                            |
             +--------------+--------------+
             |                             |
        APPLICATION                     AGENT SERVICE
          SERVICES                           |
             |                    +----------+----------+
             |                    |                     |
             |               ORCHESTRATOR         AGENT RUNTIME
             |                    |                     |
             |                    +----------+----------+
             |                               |
             |                            CLAUDE
             |
             +--------------------+----------------------+
                                  |
                           STATE / DATA LAYER
                                  |
                   +--------------+--------------+
                   |              |              |
                Postgres       pgvector      Object Storage
                   |
                Supabase
```

n8n or another workflow layer can sit beside this system for scheduled jobs and integration automation.

---

# 35. TECHNOLOGY STACK

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Framer Motion
- Recharts
- TanStack Query

Design direction:

**Linear + Notion + premium editorial analytics**

Do not design an enterprise CRM dashboard.

Prioritize clarity and decisions over chart density.

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy or equivalent ORM/data layer

## Database

- PostgreSQL
- Supabase initially
- pgvector

## Object storage

- Cloudflare R2 or S3-compatible storage

## Workflow

- n8n initially for integrations and scheduled automation
- durable workflow engine such as Temporal later if long-running agent jobs require it

## Agent framework

- LangGraph and/or Anthropic-native agent/tool patterns
- keep application architecture independent of a single agent framework where practical

## Cache / ephemeral state

- Redis where needed

## Search / research

- approved web search provider(s)
- official platform APIs
- native connectors

## Media

- FFmpeg
- transcription service/model
- image/video analysis where needed

## Analytics / observability

- PostHog
- Sentry
- OpenTelemetry

## Hosting

- Vercel for frontend
- Railway/AWS/equivalent for backend and workers

## CI/CD

- GitHub Actions

## Auth

- Supabase Auth or Clerk

## Payments later

- Stripe

---

# 36. CODEBASE ORGANIZATION

A reasonable initial structure:

```text
/apps
  /web
  /api

/services
  /agent_service
    /orchestrator
    /agents
      creator_intelligence.py
      audience.py
      research.py
      trend.py
      strategy.py
      content_architect.py
      script.py
      critic.py
      repurposing.py
      performance.py
      experimentation.py
    /context
    /memory
    /tools
    /model_router
    /schemas
    /observability

/domain
  /creator
  /content
  /research
  /strategy
  /performance
  /experiments

/infrastructure
  /db
  /storage
  /queue
  /integrations

/workflows

/tests
  /unit
  /integration
  /agent
  /evaluation
```

Do not over-engineer into many microservices before scale requires it.

---

# 37. API / DOMAIN RULES

The API should expose domain-oriented operations rather than raw agent internals.

Good:

```text
POST /creators/{id}/research
POST /creators/{id}/strategy/generate
POST /creators/{id}/opportunities
POST /content/{id}/generate-script
POST /content/{id}/review
POST /content/{id}/repurpose
GET  /creators/{id}/insights
GET  /creators/{id}/calendar
```

Avoid exposing:

```text
POST /run-agent-7
POST /call-claude
```

The model/agent implementation is internal infrastructure, not the product domain.

---

# 38. UI INFORMATION ARCHITECTURE

## Home

Answer:

> What matters this week?

Show:

- creator health
- growth movement
- what worked
- what changed
- next best opportunities
- current strategy
- blockers

## Research

Sections:

- market pulse
- competitor radar
- audience voice
- emerging topics
- content gaps
- saved signals

## Opportunities

Each card should expose:

- idea
- score
- why now
- why this creator
- audience
- competition/saturation
- format
- strategic goal
- evidence

## Create

Show:

- strategy
- brief
- hook options
- script
- critique
- rewrite
- B-roll
- CTA
- caption
- evidence

## Calendar

Show:

- week
- month
- content portfolio
- production status
- capacity

## Analytics

Prioritize:

- what changed
- why it may have changed
- what the system recommends next

## Creator DNA

Allow the creator to inspect and correct:

- voice
- positioning
- audience
- pillars
- preferences
- boundaries

The creator should be able to correct the AI's assumptions.

---

# 39. DASHBOARD DESIGN RULES

## Rule 1

Every important chart must answer a decision question.

## Rule 2

Do not show metrics without interpretation where interpretation is possible.

## Rule 3

Avoid vanity metrics as the main focus.

## Rule 4

Do not overwhelm the creator with dozens of charts.

## Rule 5

Recommendations must be editable and inspectable.

## Rule 6

The creator should always be able to ask:

> Why?

and see evidence.

---

# 40. AGENT OUTPUT CONTRACTS

Every agent should use strict structured output schemas.

At minimum:

```text
status
summary
confidence
inputs_used
evidence_ids
proposed_state_changes
next_action
warnings
```

Never depend on free-form prose parsing when a machine-readable result is possible.

Use Pydantic/JSON Schema validation.

Invalid agent outputs should fail safely and be retried or surfaced for inspection.

---

# 41. TOOL PERMISSIONS

Agents should receive only the tools they need.

Example:

```text
Creator Intelligence Agent
→ creator history
→ content library
→ profile analysis

Research Agent
→ search tools
→ platform research
→ source extraction

Strategy Agent
→ creator state
→ audience state
→ performance
→ research

Script Agent
→ creator voice
→ content memory
→ approved brief

Performance Agent
→ analytics APIs
→ performance history
```

Do not give every agent unrestricted access to every tool.

---

# 42. HUMAN-IN-THE-LOOP RULES

Require human approval for:

- final public content
- publishing
- brand-sensitive actions
- major positioning changes
- deleting data
- externally visible actions
- unclear or low-confidence strategic recommendations

Optional approval may be bypassed for:

- internal classification
- background ingestion
- non-destructive enrichment
- initial research aggregation

The creator should be able to configure automation level over time.

---

# 43. ERROR HANDLING

Agentic systems have failure modes different from standard applications.

Implement:

- retries with bounded backoff
- idempotency keys
- structured errors
- timeouts
- tool-level failure isolation
- partial result handling
- dead-letter/review mechanism where appropriate
- audit logs
- state consistency checks

Never allow a failed agent run to silently create a partial state that looks valid.

---

# 44. OBSERVABILITY

Every agent run should have a stable `agent_run_id`.

Log:

```text
agent_run_id
creator_id
agent_name
workflow_name
model
start_time
end_time
duration
input token usage
output token usage
tool calls
status
error
cost estimate
state changes
```

For important decisions, preserve enough information to reconstruct why the decision was made.

---

# 45. COST CONTROL

Track cost at:

- creator level
- workflow level
- agent level
- content level
- research job level

Use:

- caching
- batching
- deduplication
- smaller models for classification
- larger models only for high-value reasoning
- retrieval filtering
- context compression

Do not repeatedly research identical information unnecessarily.

---

# 46. SECURITY / PRIVACY

Creators may provide:

- unpublished scripts
- private ideas
- personal information
- business strategy
- audience data
- sponsorship details
- media assets

Therefore:

- isolate tenant data
- enforce authorization on every creator-scoped operation
- encrypt sensitive information appropriately
- support deletion
- do not expose one creator's data to another
- follow platform API/data retention rules
- limit internal admin access
- maintain audit logs

External platform content must be stored and processed according to applicable terms and policies.

---

# 47. RESEARCH ETHICS / DATA RULES

The research layer must distinguish:

- public signals
- connected account data
- creator-provided/private content
- inferred insights

Do not present inferred audience characteristics as directly observed facts.

Preserve uncertainty.

Respect platform access rules and deletion requirements.

Never build a strategy by copying the wording or creative expression of other creators.

---

# 48. THE DAILY CREATOR ROUTINE TEST

This is a core product requirement.

The product is not validated because agents successfully execute workflows.

It is validated only if real creators can use it as part of their daily/weekly routine and experience measurable improvement.

## Test group

Start with exactly **5 creators**.

They should represent different but relevant creator profiles.

For each creator, capture baseline information before enabling the system.

## Baseline period

Record at minimum:

- posting frequency
- time spent on research
- time spent brainstorming
- time spent scripting
- time spent scheduling
- time spent analyzing performance
- number of ideas generated
- number of ideas actually published
- number of revisions per script
- performance of recent content
- creator-reported stress/friction

## Live period

Run the Creator Intelligence OS alongside the creator's real workflow.

Do not force creators to change their behavior merely to make the software look successful.

The product must fit the creator's existing routine.

---

# 49. FIVE-CREATOR VALIDATION PROTOCOL

For each creator:

## Week 0

Observe current process.

Document:

```text
What do they do?
What tools do they use?
Where do they lose time?
Where do they get stuck?
How do they decide topics?
How do they research?
How do they write?
How do they schedule?
How do they interpret analytics?
```

## Week 1

Onboard and build Creator DNA.

Creator validates/corrects the system's understanding.

## Weeks 2–4+

Run the intelligent system continuously.

Capture:

- recommendations
- creator actions
- approvals/rejections
- edits
- published posts
- performance
- system learnings

## Every week

Ask:

1. Did the system save time?
2. Did recommendations feel relevant?
3. Did creator voice remain accurate?
4. Did the creator use the recommendations?
5. Which outputs required the most editing?
6. Did the system surface anything the creator would likely have missed?
7. Did it improve content planning?
8. Did it reduce research burden?
9. Did performance change?
10. What did the creator distrust?

---

# 50. PRODUCT VALIDATION METRICS

Do not prioritize number of AI generations.

Measure:

## Decision Velocity

Time from:

> "What should I post?"

to
> "I know exactly what I am making."

## Strategy Adoption

Percentage of recommended opportunities actually used.

## Creator Edit Rate

How much creator modification is required before publishing.

Lower is not always better; creative ownership matters.

Use it as a signal, not a sole optimization target.

## Time Saved

Research time saved.

Planning time saved.

Script-development time saved.

Analytics interpretation time saved.

## Content Output

Published content per unit of creator effort.

## Content Quality / Performance

Compare appropriate baseline metrics.

## Recommendation Validation

Percentage of recommendations that produce useful outcomes or strong creator feedback.

## Retention

Would the creator continue using the strategist?

---

# 51. NORTH-STAR PRODUCT METRIC

A candidate long-term product metric is:

> **Percentage of creator publishing decisions materially influenced by the system that are subsequently validated by performance or creator feedback.**

This measures whether the system is becoming a useful strategist rather than merely a content generator.

---

# 52. MVP SCOPE

Do NOT build the whole vision before validating the intelligence loop.

## MVP must include

1. Creator onboarding
2. Account connection where practical
3. Creator DNA generation
4. Historical content ingestion
5. Basic content understanding
6. Research engine
7. Opportunity ranking
8. Strategy generation
9. Brief generation
10. Hook + script generation
11. Critic/rewrite
12. Calendar
13. Basic performance ingestion
14. Performance diagnosis
15. Learning storage
16. Creator dashboard

## MVP can defer

- advanced automatic editing
- complex publishing automation
- broad multi-platform coverage
- sophisticated graph database
- autonomous public posting
- fully automated content creation
- deep team collaboration
- advanced monetization attribution

The core loop is more important than breadth.

---

# 53. INITIAL MVP AGENT SET

Use:

```text
Creator Intelligence Agent
Audience Intelligence Agent
Research Agent
Strategy Agent
Content Agent
Critic Agent
Performance Agent
```

Implement trend, repurposing, experimentation, and other specialized capabilities as modules/tools first unless separate agent identity clearly improves reasoning or maintainability.

---

# 54. BUILD PRIORITY ORDER

Recommended implementation order:

```text
1. Data model
2. Creator entity + tenant isolation
3. Creator onboarding
4. Content ingestion
5. Creator DNA
6. Content memory
7. Research ingestion
8. Opportunity engine
9. Strategy engine
10. Content brief
11. Script + critic loop
12. Calendar
13. Performance ingestion
14. Performance diagnosis
15. Learning engine
16. Daily creator dashboard
17. Five-creator testing
18. Refinement
19. Scale / automation
```

Do not jump to elaborate UI before proving the workflow.

---

# 55. WHAT CLAUDE CODE SHOULD OPTIMIZE FOR

When making implementation decisions, prioritize in this order:

1. Correctness
2. Creator-specific intelligence
3. Data integrity
4. Traceability
5. Reliability
6. Useful UX
7. Maintainability
8. Cost efficiency
9. Performance
10. Feature breadth

Do not sacrifice architecture integrity merely to add more visible features.

---

# 56. WHAT CLAUDE CODE SHOULD AVOID

Avoid:

- giant prompts with the whole database pasted in
- one giant `personal_context.md` as the source of truth
- direct agent-to-agent spaghetti
- unrestricted agent DB access
- hard-coded model names everywhere
- hard-coded creator-specific exceptions
- silent data overwrites
- untraceable recommendations
- hallucinated research
- copying competitors
- blindly optimizing for views
- auto-publishing by default
- unnecessary microservices
- premature graph database complexity
- huge dashboards full of vanity metrics
- generating content before understanding creator context
- treating a single viral post as a strategic truth

---

# 57. DEFINITION OF DONE FOR AN AGENT

An agent is not complete because it can generate a response.

An agent is complete when it has:

- defined inputs
- defined outputs
- strict output schema
- tool boundaries
- context requirements
- validation
- failure handling
- observability
- evidence handling where relevant
- state transition rules
- test cases
- evaluation criteria

---

# 58. DEFINITION OF DONE FOR A WORKFLOW

A workflow is complete when:

```text
Input
↓ Context retrieval
↓ Agent execution
↓ Validation
↓ State transition
↓ Persisted result
↓ User-visible result
↓ Error handling
↓ Logging
↓ Test coverage
```

all work correctly.

---

# 59. DEFINITION OF DONE FOR THE PRODUCT

The product is not considered validated because:

- the UI looks good
- Claude produces impressive scripts
- research returns many results
- the calendar works
- agents can call APIs

The product is validated only when five real creators can use it as part of their normal content workflow and measurable evidence shows that it:

- reduces strategic/research workload
- increases decision velocity
- improves content planning
- preserves creator voice
- produces useful content opportunities
- helps them learn from performance
- becomes valuable enough to retain

---

# 60. CORE USER EXPERIENCE

The ideal experience is:

### Monday

> Your strategy for this week is ready.

### Opportunity screen

> Here are the 5 strongest things you should make and why.

### Creator chooses one

> Create.

### System produces

> angle → hook → brief → script → critique → improved script

### Creator records

System provides production guidance.

### Creator publishes

### Performance arrives

> This post outperformed your baseline by X.

### System explains

> These variables appear associated with the result.

### System recommends

> Test this pattern again next week.

### Next week

The new strategy already knows what happened last week.

That is the core product experience.

---

# 61. LONG-TERM MOAT

The moat is NOT:

- Claude
- n8n
- generic prompting
- a content calendar
- a dashboard

The moat is **longitudinal Creator Intelligence**.

After months of use, the system should know:

- what this creator talks about
- how this creator talks
- who responds
- what hooks work
- what topics fail
- what stories they have already told
- what experiments were run
- what worked
- what failed
- what competitors are doing
- how the audience is evolving
- which content supports business goals

The product should increasingly feel like:

> **A strategist who has worked with this creator for years.**

---

# 62. OPERATING PHILOSOPHY FOR CLAUDE CODE

When unsure what to build, ask:

### Question 1

Does this reduce work for the creator?

### Question 2

Does this improve a content decision?

### Question 3

Does this make the system more creator-specific?

### Question 4

Does this create a persistent learning loop?

### Question 5

Can we explain why the system made the recommendation?

### Question 6

Can the creator override it?

### Question 7

Can we measure whether it worked?

If the answer to several of these is no, the feature is probably not core.

---

# 63. FINAL PRODUCT DEFINITION

The complete system is:

```text
CREATOR INTELLIGENCE
Who are you?

+

AUDIENCE INTELLIGENCE
Who are you speaking to?

+

MARKET INTELLIGENCE
What is happening?

+

STRATEGY INTELLIGENCE
What should you do?

+

CONTENT OPERATIONS
How do you execute it?

+

PERFORMANCE INTELLIGENCE
What happened?

+

LEARNING ENGINE
What should change next time?
```

Which creates the compounding loop:

```text
Creator
↓
Understand
↓
Research
↓
Opportunity
↓
Strategy
↓
Create
↓
Publish
↓
Measure
↓
Diagnose
↓
Learn
↓
Creator State updated
↓
Next Strategy
```

---

# 64. FINAL BUILD DIRECTIVE

Build an **intelligent creator engine**, not a collection of AI features.

The first real objective is to make the system useful to **five real creators in their daily routine**.

The system should eventually allow a creator to wake up and see:

> **What should I create today?**
>
> **Why should I create it?**
>
> **How should I make it?**
>
> **What should I do with the asset afterward?**
>
> **Did it work?**
>
> **What did we learn?**
>
> **What should I do next?**

Everything in the architecture should serve that loop.

When there is a conflict between adding a flashy feature and strengthening the intelligence loop, strengthen the intelligence loop.

The final product should feel less like a chatbot and more like a **persistent AI content department that knows the creator, understands the market, makes recommendations, helps execute them, and gets smarter after every post.**

---

# PART II — COMMERCIAL INTELLIGENCE / BRAND OUTBOUND LAYER

## 65. WHY THIS EXISTS

Sections 1–64 cover the Content Intelligence loop. This part adds a second,
parallel loop: brand/sponsorship discovery and outbound. It is an
**extension** of everything above, not a separate product bolted on.

```text
                    CREATOROS
                        |
              +---------+---------+
              |                   |
              v                   v
       GROWTH INTELLIGENCE   COMMERCIAL INTELLIGENCE
              |                   |
       content loop          brand outbound loop
              |                   |
              +---------+---------+
                        |
                        v
                 LEARNING ENGINE
                        |
                        v
                  CREATOR STATE
                        |
                        v
                 NEXT BEST ACTION
```

Both loops share the same Creator Brain (Creator/Audience/Content
Intelligence), the same Market Intelligence, the same Learning Engine
(`app/domain/experiments`), and the same `CreatorStateSnapshot`. Do not
duplicate any of §1–64's infrastructure to serve the commercial loop —
extend it. If you're about to create a second creator-identity table, a
second learning table, or a second evidence-provenance pattern for
commercial data, stop: reuse the existing one instead (§3.7 one source of
truth applies here too).

The commercial loop:

```text
CREATOR COMMERCIAL PROFILE
→ BRAND DISCOVERY
→ BRAND INTELLIGENCE / QUALIFICATION
→ CONTACT DISCOVERY
→ OPPORTUNITY SCORING
→ CAMPAIGN INTELLIGENCE
→ PERSONALIZED OUTREACH
→ FOLLOW-UP
→ BRAND RESPONSE
→ RESPONSE EXTRACTION
→ CREATOR DECISION
→ OUTCOME
→ COMMERCIAL LEARNING
→ CREATOR STATE
```

## 66. NON-NEGOTIABLE: THE OUTREACH AGENT NEVER DECIDES

The Outreach Agent (`app/agent_service/agents/outreach.py`) is the last agent
in the commercial pipeline. It may research, qualify, personalize, draft,
prepare follow-ups, classify a brand's response, and extract structured
information from it. It may **never**: negotiate, counteroffer, accept,
reject, promise, commit, or sign anything on the creator's behalf, or write
to a thread's `status`/`outcome`/`creator_decision` fields directly. Those
fields are written only by a route, only in response to an explicit creator
action. When a brand replies, the system stops at **CREATOR DECISION** and
presents the creator with everything needed to decide — it does not decide
for them. This is a hard constraint, enforced at the route/schema level, not
just prompt wording — treat any code path that could bypass it as a
correctness bug, not a style issue.

Default automation posture (can be relaxed later, never skipped by default):
AI researches → AI scores → AI drafts → **CREATOR APPROVES** → creator sends.

## 67. COMMERCIAL CREATOR DNA

Extends Creator State (§5), not a separate identity system. Lives in
`CommercialProfile` (`app/domain/commercial/models.py`), versioned the same
way `CreatorProfile`/`VoiceProfile` are (§7 pattern): ideal/prohibited sponsor
categories, target geographies, preferred deal formats, minimum acceptable
conditions, exclusivity/usage-right preferences, sponsorship/revenue goals,
brands to avoid. Same rule as the rest of Creator DNA: the creator can always
inspect and correct it (§3.2, §38).

## 68. BRAND ENTITIES

`app/domain/commercial/models.py`: `Brand` (creator-scoped, like
`Competitor` — see §69 for why it is *not* a shared global table),
`BrandContact`, `BrandSignal`, `BrandOpportunity`, `CampaignBrief`,
`OutreachThread`, `OutreachMessage`. Every externally-sourced fact keeps
`source`/`confidence`/`verification_state` the same way research signals and
performance data already do (§16). Never fabricate a contact, a signal, or a
specific brand event that wasn't given as evidence — same hallucination
guard as the Opportunity Engine and Content Architect (§3.6, §17.3).

## 69. MVP DATA SOURCING: MANUAL ENTRY, NOT LIVE APIS

There is no company-database, web-search, or contact-enrichment API wired
into this backend. Brand Discovery and Contact Discovery are, for now, manual
entry (creator/operator types in what they know) plus LLM reasoning over
that and existing Creator/Audience/Content/Research context — the same
pattern already used for Research Signals, content ingestion, and
performance metrics throughout this codebase. `Brand.source` distinguishes
`creator_provided` from `agent_suggested`; agent-suggested facts carry
capped confidence and must never be presented as verified. This is a
deliberate, documented choice, not an oversight — a real enrichment API can
be added later as an additional *source* without a schema change.

`Brand` is creator-scoped, not a shared global table, for the same tenant-
isolation reasons `Competitor` is (§46). Two creators tracking the same real
company get two independent rows.

## 70. OUTREACH: DRAFT-ONLY

No email-sending provider is wired in. The Outreach Agent drafts; the
creator sends the message themselves through their own email client and
marks it sent in CreatorOS; brand replies are pasted in for extraction.
`OutreachMessage.status` already models a `sent` state a future real-send
integration would transition into automatically — the human step is a
placeholder for automation, not a permanent design ceiling, but automatic
sending is out of scope until a provider is deliberately wired in with
proper reputation/compliance handling (bounces, unsubscribe, rate limits).

LinkedIn (or any platform) automated outreach is out of scope permanently
unless explicitly revisited — LinkedIn message automation violates their ToS
and risks the creator's account. A LinkedIn profile URL may be stored as a
reference field on `BrandContact`; CreatorOS never sends through it.

## 71. BRAND OPPORTUNITY SCORING

Same discipline as content Opportunity scoring (§20): component scores
computed/proposed against given evidence, the combined score computed in
code (never a model-invented aggregate), components always shown broken out
in the UI. Only score a dimension when this system actually has a groundable
data source for it — a scored dimension with nothing behind it is exactly
the "opaque number" §20 already forbids. `contactability` in particular is
always computed in code (does a verified/creator-provided contact exist on
this brand?), never proposed by the model.

## 72. COMMERCIAL LEARNING REUSES THE LEARNING ENGINE

Commercial outcomes feed `StrategicLearning` (`app/domain/experiments`,
§31/§72 of Part I) directly — a `category` value prefixed `commercial/...`
alongside the existing `performance/...` convention, same clustering,
`MIN_LEARNING_EVIDENCE` gate, and creator-override-preserving sync semantics
already built for content-performance learnings. This is what makes the
cross-loop connection real: a commercial-category learning like "AI-tool
brands outperform generic SaaS for this creator" is readable by the Strategy
Engine and Content Architect (content side) *and* by Brand Intelligence's
`historical_category_fit` scoring (commercial side) with zero additional
plumbing, because it's the same table. Do not create a second learning
table for commercial outcomes.

## 73. UI

New nav items: `Brands`, `Outreach` (see `components/nav-sidebar.tsx`). A
Creator Decision screen (brand response, structured extraction, commercial
context, the decision itself) is the key premium surface — build it to the
same "why is the system telling me this" evidentiary standard as every other
recommendation surface in this product (§3.4, §16). The Home screen's "this
week" view should eventually combine top content opportunities with
top-confidence brand opportunities side by side (§16 of the original
commercial spec) — do this once both loops have real data to show.

## 74. WHAT NOT TO BUILD

Not a generic influencer CRM. Not a marketplace. Not an autonomous sales
bot. Not mass outbound. The commercial layer exists to connect Creator →
Audience → Content → Market → Brands → Outreach → Response → Learning for
one creator at a time, with that creator making every commercial decision.
If a feature makes the system feel like "found 500 companies" instead of
"knows which brands actually make sense for me," it's off-thesis — same
test as §3.5's anti-virality-optimization rule, applied to brands instead of
content.
