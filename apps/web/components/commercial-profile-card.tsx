"use client";

import { FormEvent, useEffect, useState } from "react";
import { Briefcase } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getSession } from "@/lib/session";
import { updateCommercialProfile, ApiError } from "@/lib/api";
import type { CommercialProfileRead } from "@/lib/types";

function toCsv(list: string[] | null): string {
  return (list ?? []).join(", ");
}

function fromCsv(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function CommercialProfileCard({
  profile,
  onSaved,
}: {
  profile: CommercialProfileRead | null;
  onSaved: () => Promise<unknown>;
}) {
  const [editing, setEditing] = useState(false);
  const [idealSponsorCategories, setIdealSponsorCategories] = useState("");
  const [prohibitedCategories, setProhibitedCategories] = useState("");
  const [targetGeographies, setTargetGeographies] = useState("");
  const [preferredDealFormats, setPreferredDealFormats] = useState("");
  const [brandsToAvoid, setBrandsToAvoid] = useState("");
  const [sponsorshipGoals, setSponsorshipGoals] = useState("");
  const [revenueGoal, setRevenueGoal] = useState("");
  const [minimumConditions, setMinimumConditions] = useState("");
  const [exclusivityConstraints, setExclusivityConstraints] = useState("");
  const [usageRightsPreferences, setUsageRightsPreferences] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadFromProfile() {
    setIdealSponsorCategories(toCsv(profile?.ideal_sponsor_categories ?? null));
    setProhibitedCategories(toCsv(profile?.prohibited_categories ?? null));
    setTargetGeographies(toCsv(profile?.target_geographies ?? null));
    setPreferredDealFormats(toCsv(profile?.preferred_deal_formats ?? null));
    setBrandsToAvoid(toCsv(profile?.brands_to_avoid ?? null));
    setSponsorshipGoals(profile?.sponsorship_goals ?? "");
    setRevenueGoal(profile?.revenue_goal ?? "");
    setMinimumConditions(profile?.minimum_conditions ?? "");
    setExclusivityConstraints(profile?.exclusivity_constraints ?? "");
    setUsageRightsPreferences(profile?.usage_rights_preferences ?? "");
  }

  useEffect(() => {
    loadFromProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) {
      setError("Your session has expired — sign in again to save.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      // Always send every field's current value, including an empty string
      // or empty list — this form shows the creator's complete current
      // state at once, so a blank field means "clear this", not "leave
      // unchanged". Coercing "" to undefined here would drop the key from
      // the request entirely, and the backend treats an absent key as
      // "not proposed" (keep the old value) rather than "clear" — the two
      // must stay distinct, so never collapse empty-string to undefined.
      await updateCommercialProfile(session.creatorId, {
        ideal_sponsor_categories: fromCsv(idealSponsorCategories),
        prohibited_categories: fromCsv(prohibitedCategories),
        target_geographies: fromCsv(targetGeographies),
        preferred_deal_formats: fromCsv(preferredDealFormats),
        brands_to_avoid: fromCsv(brandsToAvoid),
        sponsorship_goals: sponsorshipGoals,
        revenue_goal: revenueGoal,
        minimum_conditions: minimumConditions,
        exclusivity_constraints: exclusivityConstraints,
        usage_rights_preferences: usageRightsPreferences,
      });
      await onSaved();
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSaving(false);
    }
  }

  const inputClass = "rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent";

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-accent" /> Commercial DNA
            </CardTitle>
            <CardDescription>
              What you can commercially offer, and the brand categories/conditions worth reasoning about — set this
              directly; it feeds brand scoring and pitch generation.
            </CardDescription>
          </div>
          {!editing && (
            <Button
              variant="secondary"
              onClick={() => {
                loadFromProfile();
                setEditing(true);
              }}
            >
              {profile ? "Edit" : "Set up"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {editing ? (
          <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Ideal sponsor categories (comma-separated)
              <input
                value={idealSponsorCategories}
                onChange={(e) => setIdealSponsorCategories(e.target.value)}
                placeholder="AI tools, productivity software"
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Prohibited categories
              <input
                value={prohibitedCategories}
                onChange={(e) => setProhibitedCategories(e.target.value)}
                placeholder="Gambling, alcohol"
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Target geographies
              <input
                value={targetGeographies}
                onChange={(e) => setTargetGeographies(e.target.value)}
                placeholder="US, UK"
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Preferred deal formats
              <input
                value={preferredDealFormats}
                onChange={(e) => setPreferredDealFormats(e.target.value)}
                placeholder="Dedicated video, integration, affiliate"
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Brands to avoid
              <input
                value={brandsToAvoid}
                onChange={(e) => setBrandsToAvoid(e.target.value)}
                placeholder="Company names"
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Revenue goal
              <input
                value={revenueGoal}
                onChange={(e) => setRevenueGoal(e.target.value)}
                placeholder="e.g. $10k/mo from sponsorships"
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle sm:col-span-2">
              Sponsorship goals
              <textarea
                value={sponsorshipGoals}
                onChange={(e) => setSponsorshipGoals(e.target.value)}
                rows={2}
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle sm:col-span-2">
              Minimum acceptable conditions
              <textarea
                value={minimumConditions}
                onChange={(e) => setMinimumConditions(e.target.value)}
                rows={2}
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Exclusivity constraints
              <textarea
                value={exclusivityConstraints}
                onChange={(e) => setExclusivityConstraints(e.target.value)}
                rows={2}
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-subtle">
              Usage rights preferences
              <textarea
                value={usageRightsPreferences}
                onChange={(e) => setUsageRightsPreferences(e.target.value)}
                rows={2}
                className={inputClass}
              />
            </label>
            <div className="flex items-center gap-3 sm:col-span-2">
              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </Button>
              {error && <span className="text-xs text-bad">{error}</span>}
            </div>
          </form>
        ) : profile ? (
          <div className="space-y-3 text-sm text-ink">
            {profile.ideal_sponsor_categories && profile.ideal_sponsor_categories.length > 0 && (
              <p>
                <span className="text-subtle">Ideal categories: </span>
                {profile.ideal_sponsor_categories.join(", ")}
              </p>
            )}
            {profile.prohibited_categories && profile.prohibited_categories.length > 0 && (
              <p>
                <span className="text-subtle">Prohibited: </span>
                {profile.prohibited_categories.join(", ")}
              </p>
            )}
            {profile.sponsorship_goals && (
              <p>
                <span className="text-subtle">Goals: </span>
                {profile.sponsorship_goals}
              </p>
            )}
            {profile.revenue_goal && (
              <p>
                <span className="text-subtle">Revenue goal: </span>
                {profile.revenue_goal}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-subtle">
            Not set up yet. This feeds brand opportunity scoring and campaign pitches once the Brands section is
            live — set it now so there's evidence to reason from.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
