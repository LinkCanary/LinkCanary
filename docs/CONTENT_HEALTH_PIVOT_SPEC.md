# LinkCanary → Content Health Monitor — Positioning & Scope Spec (v1, draft for review)

## 0. The pivot, in one paragraph

LinkCanary crawls a site, checks every link, and maps issues back to source pages — that's the scraping infrastructure. Right now it's positioned as a link checker (a Screaming Frog/Lychee competitor). The wider opportunity: run the same crawl once and surface *everything* about content health, not just links — broken links + redirect chains (have), missing/broken metadata (new), stale content (mostly have), Core Web Vitals (new). Same crawl, same infra, bigger story: "content health monitor for Astro/static sites" instead of "link checker." This is a positioning and scope change, not a rewrite.

This doc scopes what's genuinely new to build vs. what the existing crawl-engine/link_checker/linkcanary-ui already gives you for free, so you can decide what's in v1 of the pivot.

## 1. What already exists (reuse as-is)

| Capability | Where | Notes |
|---|---|---|
| Sitemap crawl, per-URL `lastmod` | `link_checker/sitemap.py` | Already parses `<lastmod>` and supports `since` filtering. This *is* the staleness signal — no new crawler work needed. |
| Broken links, redirect chains/loops, canonical mismatches | Go `crawl-engine/` + `link_checker/checker.py` | Existing core product. |
| Main-content HTML extraction | `link_checker/content_extractor.py` | Strips boilerplate, currently feeds the embedding pipeline. Same parse pass can pull metadata (see §2). |
| Semantic duplicate / off-topic detection | `link_checker/embeddings.py`, `similarity.py` | Already a "content quality" signal, just not marketed as one. |
| Crawl model + severity buckets (critical/high/medium/low) | `linkcanary_ui/models/crawl.py` | Issue counts are already generic severity buckets, not link-specific — new issue types slot in without a schema redesign. |
| CSV/HTML reports, webhooks, CI/GitHub Action | `link_checker/reporter.py`, `exporters.py`, `.github/`, `action.yml` | Delivery mechanism is done; new issue types just need to appear in the same report. |
| Migration verification | `link_checker/migration_verifier.py` | Distinct feature, unaffected by this pivot. |

**Bottom line:** ~70% of a "content health monitor" already exists under the hood. The pivot is mostly framing + two new checks.

## 2. New checks to build

### 2.1 Metadata completeness (new, small)

Extend `content_extractor.py`'s existing BeautifulSoup pass (it already parses the page once for embeddings — piggyback, don't re-fetch) to also pull:

- `<title>` — present, length (recommend 10–60 chars), duplicate across pages
- `<meta name="description">` — present, length (recommend 50–160 chars), duplicate across pages
- Canonical tag — already checked for *mismatch* by the link checker; add "missing entirely"
- OG tags (`og:title`, `og:description`, `og:image`) — present/missing
- H1 — present, exactly one, non-empty
- Image `alt` attributes — missing on `<img>` (cheap accessibility/SEO signal, same DOM pass)

Each becomes a new issue type in the existing severity taxonomy (e.g. missing title/H1 = high, missing OG image = low, duplicate title = medium). No new dependency — this is fields added to a parse that already happens per page.

### 2.2 Outdated content flag (new, but mostly wiring)

`sitemap.py` already has `lastmod` per URL. Add:

- A configurable staleness threshold (e.g. "flag pages with no `lastmod` update in 12 months") — per-crawl setting, same pattern as the existing `since_date` field on `Crawl`.
- Fallback when `lastmod` is absent: none — don't guess from HTTP headers or scrape dates out of page text, that's a rabbit hole. Sites without sitemap `lastmod` simply don't get this check; document the limitation.

This is a threshold comparison on data you already have, not a new crawl capability.

### 2.3 Core Web Vitals (new, real dependency)

This is the one genuinely new piece of infrastructure. Two options:

- **Recommended: Google PageSpeed Insights API** (free tier, no infra to run). One HTTP call per URL, returns lab data (LCP, CLS, INP/FID, TTFB) plus a Lighthouse score. Rate-limited (~25k free req/day with an API key) — fine for periodic site audits, not for every page on every crawl of a large site by default.
- Alternative: self-hosted Lighthouse CI in the Go/Python worker — more control, real infra to run and maintain (headless Chrome), not worth it for v1.

**v1 scope:** call PageSpeed Insights for a sampled subset of pages per crawl (e.g. top N by internal link count, or user-specified URLs), not every page — keeps it inside the free tier and keeps crawl time sane. Store per-page CWV scores alongside the existing per-crawl issue counts. Surface pass/fail against Google's published thresholds (LCP ≤2.5s, CLS ≤0.1, INP ≤200ms) as the new severity-bucketed issue.

## 3. Data model changes

Additive only — no breaking changes to `Crawl`:

- `Crawl` (or a new `crawl_settings` sub-object, matching the existing `CrawlSettings` pydantic pattern in `schemas.py`): add `check_metadata: bool`, `staleness_days: Optional[int]`, `check_cwv: bool`, `cwv_sample_urls: Optional[list[str]]`.
- New issue rows follow the existing severity model — no new table needed if issues are already stored generically; if they're currently link-specific rows, add a `type` discriminator (`link`, `metadata`, `staleness`, `cwv`) so the report/reporter code can group by category.
- CWV results: one small table or JSON column keyed by crawl_id + url, since PageSpeed responses are a fixed small shape (scores + 3 metrics) — doesn't need its own migration-heavy model.

## 4. Report / UI changes

- Report should group by **category** (Links / Metadata / Freshness / Performance) instead of one flat issue list — this is the visible expression of the pivot, more than any backend change.
- Dashboard summary: instead of one "issues found" number, four category tiles (mirrors the four bullet points in your ask: broken links, redirect chains, missing metadata, outdated content — CWV as a fifth).
- CSV export: add columns for issue `type`/`category` so existing CI consumers aren't broken (additive column, not a schema change to existing ones).

## 5. Positioning changes (out of code scope, flagging for your content-plan pass)

Not implementation, but the pivot doesn't land without it:

- README/landing copy: "Content health monitor for Astro & static sites" as the headline, link-checking as one of five checks rather than the whole product.
- Comparison table (`README.md` already has one vs. Screaming Frog/Lychee) needs a new row set: neither of those competitors do metadata/staleness/CWV in one pass — that's the differentiation, not link-checking speed.
- This aligns with, doesn't conflict with, the existing `docs/SAAS_MIGRATION_SPEC.md` v2 scope ("continuous monitoring engine" was already planned) — this pivot is about *what* gets monitored, that spec is about *how* it's sold/run continuously. Worth merging the two roadmaps before building v2 billing/scheduling so you don't scope continuous monitoring around only-links and have to redo it for content health.

## 6. Phasing recommendation

1. **Metadata checks** — cheapest, reuses the existing parse pass, no new dependency. Ship first.
2. **Staleness flag** — cheapest, reuses existing `lastmod` data. Ship alongside #1.
3. **Report/UI regrouping by category** — needed to make #1/#2 visible as "content health" rather than buried in the link report.
4. **Core Web Vitals via PageSpeed API, sampled** — real new integration, do last, behind a feature flag/opt-in setting since it adds external API latency to a crawl.
5. **Positioning/copy pass** — README, landing page, comparison table — can happen in parallel with #1–#3 once the category grouping exists to point to.

## 7. Open questions for you

- Staleness default threshold — 6mo? 12mo? Configurable per-crawl either way, just need a default.
- CWV sampling strategy — top-N by internal links, explicit URL list, or "homepage + top-level pages only"? Affects PageSpeed API quota usage.
- Does "Content Health Monitor" replace the LinkCanary name/brand, or sit as a new report mode under the existing brand? (No code impact either way, but changes the README/landing rewrite scope in §5.)
