"use client";

import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Building2, Users, Radar, Sparkles, Megaphone } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import {
  addBrandContact,
  addBrandSignal,
  createBrand,
  createOutreachThread,
  generateCampaignBrief,
  getBrand,
  getCampaignBrief,
  listBrandContacts,
  listBrandRadar,
  listBrandSignals,
  listBrands,
  scoreBrandOpportunity,
  ApiError,
} from "@/lib/api";
import type { BrandContactRead, BrandRadarItem, BrandRead, BrandSignalRead, CampaignBriefRead } from "@/lib/types";
import { SkeletonText, SkeletonCard } from "@/components/ui/skeleton";

const inputClass = "rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent";

function scoreTone(score: number | null): "good" | "warn" | "neutral" {
  if (score === null) return "neutral";
  if (score >= 0.7) return "good";
  if (score >= 0.4) return "warn";
  return "neutral";
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  return <Badge tone={scoreTone(score)}>{Math.round(score * 100)}/100</Badge>;
}

function BulletList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-subtle">{label}</p>
      <ul className="list-disc space-y-0.5 pl-5">
        {items.map((item, i) => (
          // Index-keyed alongside the text: the model can repeat a string
          // across two distinct deliverables/facts, and a bare text key
          // would then collide and let React reuse/misrender a list node.
          <li key={`${i}-${item}`} className="text-ink">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function BrandsPage() {
  return (
    <Suspense
      fallback={
        <div>
          <PageHeader title="Brands" description="Brand Radar — which brands actually make sense for you, and why." />
          <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        </div>
      }
    >
      <BrandsPageInner />
    </Suspense>
  );
}

function AddBrandForm({ onAdded }: { onAdded: (brand: BrandRead) => void }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      const brand = await createBrand(session.creatorId, {
        name,
        category: category || undefined,
        website: website || undefined,
        description: description || undefined,
      });
      setName("");
      setCategory("");
      setWebsite("");
      setDescription("");
      onAdded(brand);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-accent" /> Add a brand
        </CardTitle>
        <CardDescription>
          A company you think could be a genuine fit — no live company database is connected yet, so start with what
          you already know (CLAUDE.md §69).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Brand name"
            className={inputClass}
          />
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Category (e.g. AI productivity tools)"
            className={inputClass}
          />
          <input
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="Website (optional)"
            className={inputClass}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What do they do? (optional)"
            className={inputClass}
          />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add brand"}
            </Button>
            {error && <span className="ml-3 text-xs text-bad">{error}</span>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function AddContactForm({
  brandId,
  onAdded,
  prefillRole,
}: {
  brandId: string;
  onAdded: (c: BrandContactRead) => void;
  prefillRole?: string | null;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("");
  const [profileUrl, setProfileUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  // A click on one of the agent-suggested contact roles (Fit score card)
  // prefills and refocuses this form instead of just being inert text the
  // creator has to retype — the whole point of surfacing role suggestions
  // is to make contact entry faster, not just informative.
  useEffect(() => {
    if (!prefillRole) return;
    setRole(prefillRole);
    nameInputRef.current?.focus();
  }, [prefillRole]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      const contact = await addBrandContact(session.creatorId, brandId, {
        name: name || undefined,
        role: role || undefined,
        email: email || undefined,
        profile_url: profileUrl || undefined,
        verification_state: "creator_provided",
      });
      setName("");
      setRole("");
      setEmail("");
      setProfileUrl("");
      onAdded(contact);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <input
        ref={nameInputRef}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name"
        className={inputClass}
      />
      <input
        value={role}
        onChange={(e) => setRole(e.target.value)}
        placeholder="Role (e.g. Creator Partnerships)"
        className={inputClass}
      />
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email (if known)" className={inputClass} />
      <input
        value={profileUrl}
        onChange={(e) => setProfileUrl(e.target.value)}
        placeholder="LinkedIn / profile URL"
        className={inputClass}
      />
      <div className="sm:col-span-2">
        <Button type="submit" variant="secondary" disabled={submitting}>
          {submitting ? "Adding…" : "Add contact"}
        </Button>
        {error && <span className="ml-3 text-xs text-bad">{error}</span>}
      </div>
    </form>
  );
}

function AddSignalForm({ brandId, onAdded }: { brandId: string; onAdded: (s: BrandSignalRead) => void }) {
  const [summary, setSummary] = useState("");
  const [signalType, setSignalType] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      const signal = await addBrandSignal(session.creatorId, brandId, {
        summary,
        signal_type: signalType || undefined,
      });
      setSummary("");
      setSignalType("");
      onAdded(signal);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-2 sm:grid-cols-[140px_1fr_auto]">
      <select value={signalType} onChange={(e) => setSignalType(e.target.value)} className={inputClass}>
        <option value="">Type</option>
        <option value="product_launch">Product launch</option>
        <option value="campaign_launch">Campaign launch</option>
        <option value="new_market">New market</option>
        <option value="hiring">Hiring</option>
        <option value="competitor_creator_activity">Competitor creator activity</option>
        <option value="funding">Funding</option>
        <option value="seasonal">Seasonal</option>
        <option value="other">Other</option>
      </select>
      <input
        required
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="What did you observe? e.g. 'Launched a creator ambassador program.'"
        className={inputClass}
      />
      <Button type="submit" variant="secondary" disabled={submitting}>
        {submitting ? "Adding…" : "Add signal"}
      </Button>
      {error && <span className="text-xs text-bad sm:col-span-3">{error}</span>}
    </form>
  );
}

function BrandsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("brand"));
  const [selected, setSelected] = useState<BrandRead | null>(null);
  const [contacts, setContacts] = useState<BrandContactRead[]>([]);
  const [signals, setSignals] = useState<BrandSignalRead[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [radar, setRadar] = useState<BrandRadarItem[]>([]);
  const [loadingRadar, setLoadingRadar] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [scoreWarnings, setScoreWarnings] = useState<string[]>([]);
  const [contactRolePrefill, setContactRolePrefill] = useState<string | null>(null);
  const [campaignBrief, setCampaignBrief] = useState<CampaignBriefRead | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(false);
  const [generatingBrief, setGeneratingBrief] = useState(false);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [briefWarnings, setBriefWarnings] = useState<string[]>([]);
  const [startingOutreach, setStartingOutreach] = useState(false);
  const [outreachError, setOutreachError] = useState<string | null>(null);
  const [outreachWarnings, setOutreachWarnings] = useState<string[]>([]);

  const refetchBrands = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoadingList(false);
      return;
    }
    setLoadingList(true);
    try {
      setBrands(await listBrands(session.creatorId));
    } finally {
      setLoadingList(false);
    }
  }, []);

  const refetchRadar = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoadingRadar(false);
      return;
    }
    setLoadingRadar(true);
    try {
      setRadar(await listBrandRadar(session.creatorId));
    } finally {
      setLoadingRadar(false);
    }
  }, []);

  useEffect(() => {
    refetchBrands();
    refetchRadar();
  }, [refetchBrands, refetchRadar]);

  const currentOpportunity = selected ? radar.find((r) => r.brand.id === selected.id)?.opportunity ?? null : null;

  // Keyed on the opportunity id (not selectedId) so it naturally clears when
  // switching to a brand with no score yet, and re-fetches after a brand
  // gets scored for the first time (currentOpportunity flips from null to
  // an id) without needing a separate reset in selectBrand.
  const opportunityId = currentOpportunity?.id ?? null;
  // Tracks the latest opportunityId outside of any single effect/handler's
  // closure so an in-flight request started for a brand the creator has
  // since navigated away from can detect that at resolution time, instead
  // of overwriting the now-displayed brand's card with a stale result.
  const opportunityIdRef = useRef(opportunityId);
  useEffect(() => {
    opportunityIdRef.current = opportunityId;
  }, [opportunityId]);

  useEffect(() => {
    if (!opportunityId) {
      setCampaignBrief(null);
      return;
    }
    const session = getSession();
    if (!session) return;
    let cancelled = false;
    setLoadingBrief(true);
    getCampaignBrief(session.creatorId, opportunityId)
      .then((brief) => {
        if (!cancelled) setCampaignBrief(brief);
      })
      .catch((err) => {
        if (!cancelled) setBriefError(err instanceof ApiError ? err.message : "Couldn't load the campaign pitch.");
      })
      .finally(() => {
        if (!cancelled) setLoadingBrief(false);
      });
    return () => {
      cancelled = true;
    };
  }, [opportunityId]);

  async function handleGenerateBrief() {
    const session = getSession();
    if (!session || !opportunityId) return;
    const requestedFor = opportunityId;
    setGeneratingBrief(true);
    setBriefError(null);
    setBriefWarnings([]);
    try {
      const result = await generateCampaignBrief(session.creatorId, requestedFor);
      // The creator may have selected a different brand while this request
      // was in flight — a stale response must not overwrite what's now on
      // screen for a brand this result has nothing to do with.
      if (opportunityIdRef.current !== requestedFor) return;
      setBriefWarnings(result.warnings);
      if (result.brief) setCampaignBrief(result.brief);
    } catch (err) {
      if (opportunityIdRef.current !== requestedFor) return;
      setBriefError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      if (opportunityIdRef.current === requestedFor) setGeneratingBrief(false);
    }
  }

  async function handleStartOutreach() {
    const session = getSession();
    if (!session || !opportunityId) return;
    const requestedFor = opportunityId;
    setStartingOutreach(true);
    setOutreachError(null);
    setOutreachWarnings([]);
    try {
      // Address it to a contact already on file when one exists — the
      // whole point of tracking a contact is so outreach gets personalized
      // to them instead of drafting a generic "Hi there".
      const result = await createOutreachThread(session.creatorId, requestedFor, contacts[0]?.id);
      if (opportunityIdRef.current !== requestedFor) return;
      if (result.thread) {
        router.push(`/outreach?thread=${result.thread.id}`);
        return;
      }
      setOutreachWarnings(result.warnings);
    } catch (err) {
      if (opportunityIdRef.current !== requestedFor) return;
      setOutreachError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      if (opportunityIdRef.current === requestedFor) setStartingOutreach(false);
    }
  }

  async function handleScore() {
    const session = getSession();
    if (!session || !selected) return;
    setScoring(true);
    setScoreError(null);
    setScoreWarnings([]);
    try {
      const result = await scoreBrandOpportunity(session.creatorId, selected.id);
      // Warnings (e.g. a prohibited-category conflict) matter just as much
      // on a successful score as on a skipped one — surface them either way
      // rather than only when scoring produced nothing.
      setScoreWarnings(result.warnings);
      if (result.opportunity) {
        const opp = result.opportunity;
        setRadar((prev) => {
          const withoutThis = prev.filter((r) => r.brand.id !== selected.id);
          return [...withoutThis, { brand: selected, opportunity: opp }].sort(
            (a, b) => (b.opportunity.score ?? 0) - (a.opportunity.score ?? 0)
          );
        });
      }
    } catch (err) {
      setScoreError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setScoring(false);
    }
  }

  // Selecting only updates id/URL/cleared-state synchronously; fetching the
  // detail is a separate effect below keyed on selectedId — this is what
  // makes a direct load of /brands?brand=X (bookmark, refresh) actually
  // fetch on mount, since selectedId's useState initializer already reads
  // the query param before any effect runs (mirrors app/create/page.tsx's
  // selectItem/refetchDetail split).
  const selectBrand = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      setSelected(null);
      setContacts([]);
      setSignals([]);
      setScoreError(null);
      setScoreWarnings([]);
      setContactRolePrefill(null);
      setBriefError(null);
      setBriefWarnings([]);
      setOutreachError(null);
      setOutreachWarnings([]);
      router.replace(id ? `/brands?brand=${id}` : "/brands");
    },
    [router]
  );

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    async function loadDetail() {
      const session = getSession();
      if (!session) return;
      setLoadingDetail(true);
      try {
        const [brand, brandContacts, brandSignals] = await Promise.all([
          getBrand(session.creatorId, selectedId as string),
          listBrandContacts(session.creatorId, selectedId as string),
          listBrandSignals(session.creatorId, selectedId as string),
        ]);
        // Guards against a slower response for a previously-selected brand
        // resolving after a faster response for the newly-selected one and
        // overwriting it with the wrong brand's data.
        if (cancelled) return;
        setSelected(brand);
        setContacts(brandContacts);
        setSignals(brandSignals);
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // Next.js App Router reuses this component instance across query-string-
  // only navigations on the same /brands route, so selectedId's one-time
  // useState initializer needs this sync for any later URL change (e.g. a
  // link elsewhere pointing at a different ?brand=). Stays loop-free once
  // synced: after selectBrand's router.replace, paramBrand === selectedId.
  const paramBrand = searchParams.get("brand");
  useEffect(() => {
    if (paramBrand !== selectedId) selectBrand(paramBrand);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramBrand]);

  return (
    <div>
      <PageHeader title="Brands" description="Brand Radar — which brands actually make sense for you, and why." />
      <div className="p-8 pb-0">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radar className="h-4 w-4 text-accent" /> Brand Radar
            </CardTitle>
            <CardDescription>Ranked by fit — score a brand from its detail panel below to add it here.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loadingRadar ? (
              <div className="p-4"><SkeletonText lines={2} /></div>
            ) : radar.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  icon={Radar}
                  title="No scored brands yet"
                  description="Add a brand below, then score it to see why it might (or might not) be a fit."
                />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {radar.map(({ brand, opportunity }) => (
                  <li key={brand.id}>
                    <button
                      onClick={() => selectBrand(brand.id)}
                      className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-ink/5"
                    >
                      <div>
                        <p className="text-sm font-medium text-ink">{brand.name}</p>
                        <p className="text-xs text-subtle">{opportunity.reasons ?? brand.category ?? "—"}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {opportunity.prohibited_conflict && <Badge tone="bad">prohibited category</Badge>}
                        <ScoreBadge score={opportunity.score} />
                        <ConfidenceBadge confidence={opportunity.confidence} />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-4">
          <AddBrandForm
            onAdded={(brand) => {
              setBrands((prev) => [brand, ...prev]);
              selectBrand(brand.id);
            }}
          />
          <Card>
            <CardHeader>
              <CardTitle>Your brands</CardTitle>
              <CardDescription>{brands.length} tracked</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {loadingList ? (
                <div className="p-4"><SkeletonText lines={2} /></div>
              ) : brands.length === 0 ? (
                <div className="p-4">
                  <EmptyState icon={Building2} title="No brands yet" description="Add one above to get started." />
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {brands.map((b) => (
                    <li key={b.id}>
                      <button
                        onClick={() => selectBrand(b.id)}
                        className={`flex w-full items-center justify-between px-4 py-3 text-left text-sm hover:bg-ink/5 ${
                          selectedId === b.id ? "bg-accent-soft" : ""
                        }`}
                      >
                        <span className="text-ink">{b.name}</span>
                        <Badge tone="neutral">{b.category ?? "—"}</Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div>
          {!selectedId ? (
            <Card>
              <CardContent className="p-8">
                <EmptyState
                  icon={Radar}
                  title="Select a brand"
                  description="Pick a brand from the list to see its detail, contacts, and signals."
                />
              </CardContent>
            </Card>
          ) : loadingDetail || !selected ? (
            <Card>
              <CardContent className="p-8"><SkeletonText lines={2} /></CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle>{selected.name}</CardTitle>
                      <CardDescription>{selected.category ?? "No category set"}</CardDescription>
                    </div>
                    <Badge tone={selected.source === "creator_provided" ? "neutral" : "warn"}>
                      {selected.source === "creator_provided" ? "your entry" : "AI-suggested — verify"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-ink">
                  {selected.website && (
                    <p>
                      <span className="text-subtle">Website: </span>
                      {selected.website}
                    </p>
                  )}
                  {selected.description && <p>{selected.description}</p>}
                  {!selected.website && !selected.description && (
                    <p className="text-subtle">No further detail yet.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-accent" /> Fit score
                      </CardTitle>
                      <CardDescription>Why this brand might (or might not) be worth pursuing.</CardDescription>
                    </div>
                    <Button variant="secondary" onClick={handleScore} disabled={scoring}>
                      {scoring ? "Scoring…" : currentOpportunity ? "Re-score" : "Score this brand"}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {scoreError && <p className="text-sm text-bad">{scoreError}</p>}
                  {scoreWarnings.length > 0 && (
                    <p className="text-sm text-warn">{scoreWarnings.join(" ")}</p>
                  )}
                  {currentOpportunity ? (
                    <>
                      <div className="flex items-center gap-2">
                        {currentOpportunity.prohibited_conflict && (
                          <Badge tone="bad">prohibited category</Badge>
                        )}
                        <ScoreBadge score={currentOpportunity.score} />
                        <ConfidenceBadge confidence={currentOpportunity.confidence} />
                      </div>
                      {currentOpportunity.score_components && (
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(currentOpportunity.score_components).map(([key, value]) => (
                            <Badge key={key} tone="neutral">
                              {key.replace(/_/g, " ")}: {Math.round(value * 100)}
                            </Badge>
                          ))}
                        </div>
                      )}
                      {currentOpportunity.reasons && <p className="text-sm text-ink">{currentOpportunity.reasons}</p>}
                      {currentOpportunity.suggested_contact_roles.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-sm text-subtle">Worth looking for — click to start a contact:</p>
                          <div className="flex flex-wrap gap-1.5">
                            {currentOpportunity.suggested_contact_roles.map((role) => (
                              <button
                                key={role}
                                type="button"
                                onClick={() => setContactRolePrefill(role)}
                                className="rounded-full border border-border px-2.5 py-1 text-xs text-ink hover:border-accent hover:text-accent"
                              >
                                + {role}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    !scoreError && scoreWarnings.length === 0 && (
                      <p className="text-sm text-subtle">Not scored yet.</p>
                    )
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Megaphone className="h-4 w-4 text-accent" /> Campaign pitch
                      </CardTitle>
                      <CardDescription>A draft starting point — nothing here is sent or agreed to until you say so.</CardDescription>
                    </div>
                    {currentOpportunity && (
                      <Button variant="secondary" onClick={handleGenerateBrief} disabled={generatingBrief}>
                        {generatingBrief ? "Drafting…" : campaignBrief ? "Regenerate" : "Create pitch"}
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {!currentOpportunity && (
                    <p className="text-sm text-subtle">Score this brand first, then draft a pitch from the result.</p>
                  )}
                  {briefError && <p className="text-sm text-bad">{briefError}</p>}
                  {briefWarnings.length > 0 && <p className="text-sm text-warn">{briefWarnings.join(" ")}</p>}
                  {loadingBrief && <SkeletonText lines={2} />}
                  {campaignBrief && (
                    <div className="space-y-2.5 text-sm">
                      {campaignBrief.campaign_concept && (
                        <p className="font-medium text-ink">{campaignBrief.campaign_concept}</p>
                      )}
                      {campaignBrief.pitch_angle && (
                        <p className="italic text-subtle">&ldquo;{campaignBrief.pitch_angle}&rdquo;</p>
                      )}
                      {campaignBrief.objective_hypothesis && (
                        <p><span className="text-subtle">Objective: </span>{campaignBrief.objective_hypothesis}</p>
                      )}
                      {campaignBrief.content_format && (
                        <p><span className="text-subtle">Format: </span>{campaignBrief.content_format}</p>
                      )}
                      {campaignBrief.why_this_brand && (
                        <p><span className="text-subtle">Why this brand: </span>{campaignBrief.why_this_brand}</p>
                      )}
                      {campaignBrief.why_now && (
                        <p><span className="text-subtle">Why now: </span>{campaignBrief.why_now}</p>
                      )}
                      {campaignBrief.suggested_cta && (
                        <p><span className="text-subtle">Suggested CTA: </span>{campaignBrief.suggested_cta}</p>
                      )}
                      <BulletList
                        label="Proposed deliverables — a starting point to negotiate, not a commitment:"
                        items={campaignBrief.suggested_deliverables ?? []}
                      />
                      <BulletList label="Worth mentioning in outreach:" items={campaignBrief.personalization_facts ?? []} />
                      <ConfidenceBadge confidence={campaignBrief.confidence} />
                      <div className="pt-1">
                        <Button onClick={handleStartOutreach} disabled={startingOutreach}>
                          {startingOutreach ? "Drafting outreach…" : "Start outreach"}
                        </Button>
                        {outreachError && <p className="mt-2 text-sm text-bad">{outreachError}</p>}
                        {outreachWarnings.length > 0 && (
                          <p className="mt-2 text-sm text-warn">{outreachWarnings.join(" ")}</p>
                        )}
                      </div>
                    </div>
                  )}
                  {!campaignBrief && !loadingBrief && currentOpportunity && !briefError && briefWarnings.length === 0 && (
                    <p className="text-sm text-subtle">No pitch drafted yet.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-accent" /> Contacts
                  </CardTitle>
                  <CardDescription>Never invented — every contact here is what you entered.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <AddContactForm
                    brandId={selected.id}
                    onAdded={(c) => {
                      setContacts((prev) => [c, ...prev]);
                      setContactRolePrefill(null);
                    }}
                    prefillRole={contactRolePrefill}
                  />
                  {contacts.length === 0 ? (
                    <p className="text-sm text-subtle">No contacts yet.</p>
                  ) : (
                    <ul className="divide-y divide-border">
                      {contacts.map((c) => (
                        <li key={c.id} className="flex items-center justify-between py-2 text-sm">
                          <div>
                            <p className="text-ink">{c.name ?? "Unnamed contact"}</p>
                            <p className="text-xs text-subtle">{c.role ?? "—"}</p>
                          </div>
                          <Badge tone={c.verification_state === "verified" ? "good" : "neutral"}>
                            {c.verification_state}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Radar className="h-4 w-4 text-accent" /> Signals
                  </CardTitle>
                  <CardDescription>What you've observed about this brand — the evidence future scoring reads from.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <AddSignalForm brandId={selected.id} onAdded={(s) => setSignals((prev) => [s, ...prev])} />
                  {signals.length === 0 ? (
                    <p className="text-sm text-subtle">No signals yet.</p>
                  ) : (
                    <ul className="divide-y divide-border">
                      {signals.map((s) => (
                        <li key={s.id} className="py-2 text-sm">
                          <div className="flex items-center gap-2">
                            {s.signal_type && <Badge tone="accent">{s.signal_type}</Badge>}
                            <span className="text-ink">{s.summary}</span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
