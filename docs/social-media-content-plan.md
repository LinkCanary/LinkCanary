# LinkCanary — 3-Month Social Media Content Plan
## LinkedIn & BlueSky | May–July 2026

---

## Strategy Overview

### Goals
- Build awareness of LinkCanary in developer, SEO, and content engineering communities
- Position LinkCanary as automation infrastructure, not just a link checker
- Draw direct comparisons to Screaming Frog and Lychee to capture organic search interest
- Drive GitHub stars, installs, and community contributions

### Audience Segments
| Segment | Platform Focus | Pain Points to Address |
|---|---|---|
| Developers / DevOps | BlueSky, LinkedIn | Broken links slipping into prod, no CI hook |
| SEO professionals | LinkedIn | Screaming Frog desktop bottleneck, redirect chains |
| Content / editorial teams | LinkedIn | No context for broken links after migrations |
| Agency / consultant | LinkedIn | Client reporting overhead, staging auth hurdles |
| Open-source enthusiasts | BlueSky | Vendor lock-in, self-hosting, MIT license |

### Posting Cadence
- **LinkedIn**: 2 posts/week (Tuesday + Thursday)
- **BlueSky**: 3–4 posts/week (Monday, Wednesday, Friday + optional weekend dev tip)

### Tone
- **LinkedIn**: Professional, data-informed, outcome-focused. Think "engineering manager sharing a lesson learned."
- **BlueSky**: Casual, developer-native, slightly opinionated. Think "senior dev in Slack."

### Recurring Content Formats
- **Feature Spotlight** — Deep-dive on one capability per week
- **vs. Post** — Direct comparison to Screaming Frog or Lychee
- **Real-world scenario** — Story-driven "we had this problem, here's how we solved it"
- **Quick tip** — CLI one-liner or config trick (BlueSky-heavy)
- **Open question** — Engagement driver ("How do you currently catch broken links?")
- **Behind the build** — Why a feature was built the way it was

---

## Month 1: Awareness & Problem Definition
**Theme: "Broken links are a workflow problem, not just an audit problem"**

The first month establishes what LinkCanary is, who it's for, and why existing tools leave gaps. Emphasis on the core problem before the solution.

---

### Week 1 — Launch / Introduction

**LinkedIn (Tuesday)**
> **Post type:** Announcement / story
>
> Title: "We built LinkCanary because no existing tool fit our CI pipeline."
>
> Body:
> Every site migration ends the same way: hundreds of broken links found weeks after launch, with no record of which pages they came from.
>
> We tried Screaming Frog. It's a great desktop tool — but it can't run in a GitHub Action. You can't automate it. You can't fail a PR build with it. You export a CSV and manually triage.
>
> We tried Lychee. Fast, Rust-based, great for raw speed. But it gives you a list of broken URLs with zero context. You know that /old-post is broken. You don't know it appears on 47 pages.
>
> So we built LinkCanary — an open-source link auditor with occurrence tracking, CI/CD integration, and enough export formats to satisfy every stakeholder.
>
> MIT licensed. Self-hosted. No per-URL pricing.
>
> [link to repo]
>
> **Hashtags:** #WebDev #SEO #OpenSource #DevOps #CI

---

**BlueSky (Monday)**
> **Post type:** Introduction thread (3 posts)
>
> 1/ Just shipped LinkCanary — open-source link auditing with one feature I've never seen in any other tool:
>
> **Occurrence tracking.** Not just "this URL is broken" but "this URL is broken and appears on 43 pages."
>
> 2/ Why does that matter?
>
> Most sites have 5–10 broken links that appear everywhere (nav, footer, template). Fix those 10 URLs and you clear 80% of your issues.
>
> Without occurrence data you're triaging blind.
>
> 3/ It also runs as a GitHub Action, exports to CSV/HTML/Excel/PDF/Google Sheets, and supports Basic Auth for staging environments.
>
> MIT, self-hosted, no SaaS pricing surprises.
>
> github: [repo link]

---

**BlueSky (Wednesday)**
> **Post type:** Open question
>
> How do you currently catch broken links before they hit production?
>
> A) Manual check before launch
> B) User reports after launch
> C) Automated CI check
> D) Screaming Frog on a schedule
>
> (Asking for very research-y reasons 🐦)

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> linkcheck quick-start:
>
> ```
> pip install linkcanary
> linkcheck --sitemap https://yoursite.com/sitemap.xml
> ```
>
> That's it. You get a prioritized list of broken links with occurrence counts in ~2 minutes.
>
> Add `--format html` for a shareable report.

---

### Week 2 — The Problem with Manual Audits

**LinkedIn (Tuesday)**
> **Post type:** Thought leadership / comparison setup
>
> Title: "Your link audit is already out of date."
>
> Body:
> The problem with tools like Screaming Frog isn't the tool itself — it's the workflow it forces on you.
>
> You run it manually. You export a CSV. You email it to someone. Two weeks pass. The site changes. Your audit is stale.
>
> Meanwhile broken links are accumulating in navigation menus, blog footers, and CTAs you touched six months ago and forgot about.
>
> Link health isn't a quarterly audit. It's a signal that should be part of your deployment pipeline the same way test coverage is.
>
> This is why we built LinkCanary as automation infrastructure first. The CLI, the GitHub Action, the scheduled crawl — they exist so that you don't have to remember to run the audit.
>
> The audit runs every time you ship.
>
> **Hashtags:** #SEO #WebDev #CI #DevOps #ContentOps

---

**LinkedIn (Thursday)**
> **Post type:** Feature spotlight — GitHub Actions integration
>
> Title: "Fail the PR. Don't merge broken links."
>
> Body:
> Here's a GitHub Actions workflow that blocks a merge if any new broken links are detected:
>
> ```yaml
> - uses: linkcanary/linkcanary-action@v1
>   with:
>     sitemap-url: 'https://staging.yoursite.com/sitemap.xml'
>     fail-on-issues: true
>     auth-username: ${{ secrets.STAGING_USER }}
>     auth-password: ${{ secrets.STAGING_PASS }}
> ```
>
> This runs against your staging URL on every PR, supports Basic Auth for protected environments, and exits with code 1 if issues are found — which fails the GitHub Actions check.
>
> No Screaming Frog license. No scheduled reminder. No "I'll check it after deploy."
>
> **Hashtags:** #GitHub #DevOps #WebDev #CI #OpenSource

---

**BlueSky (Monday)**
> **Post type:** Real-world scenario
>
> A site I know migrated from Squarespace to Ghost.
>
> 3 months later: 200+ broken links. Mostly in the blog footer template. Every single post was affected.
>
> A traditional audit gives you: "these 200 URLs are broken."
>
> LinkCanary gives you: "this 1 URL is broken on 214 pages — fix the footer template."
>
> That's occurrence tracking. That's the whole point.

---

**BlueSky (Wednesday)**
> **Post type:** Quick comparison
>
> Screaming Frog vs LinkCanary in CI:
>
> Screaming Frog: ❌ desktop app, ❌ no CLI, ❌ no GitHub Action, ❌ can't fail a build
>
> LinkCanary: ✅ CLI, ✅ GitHub Action, ✅ Docker, ✅ exit codes, ✅ Basic Auth for staging
>
> Different tools for different workflows. SF is great for one-off desktop audits. LC is for teams that ship continuously.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> Did a deploy and only want to check pages that changed?
>
> ```
> git diff --name-only HEAD~1 | grep content/ > changed.txt
> linkcheck --url-file changed.txt --base-url https://yoursite.com
> ```
>
> `--url-file` lets you check specific pages instead of the full sitemap. Perfect for PR checks on large sites.

---

### Week 3 — Occurrence Tracking Deep Dive

**LinkedIn (Tuesday)**
> **Post type:** Feature spotlight — occurrence tracking
>
> Title: "The one metric that changes how you prioritize broken links."
>
> Body:
> Every link checker gives you a list of broken URLs. None of them (that I've found) tell you where those broken URLs appear.
>
> That distinction matters more than you'd think.
>
> A broken link on one obscure blog post from 2019: low priority.
> A broken link in your site navigation that appears on every page: fix it now.
>
> LinkCanary tracks occurrences. For every broken or redirecting URL it finds, it maps back every page on your site that contains that link. The report sorts by occurrence count — highest impact issues first.
>
> This turns a 500-row spreadsheet into a 10-item punch list.
>
> **Hashtags:** #SEO #ContentStrategy #WebDev #LinkBuilding #TechnicalSEO

---

**LinkedIn (Thursday)**
> **Post type:** vs. post — Lychee comparison
>
> Title: "Lychee is faster than LinkCanary. Here's why we built LinkCanary anyway."
>
> Body:
> Lychee is a Rust-based link checker. It's genuinely fast — much faster than Python. For a 100,000-URL site, that matters.
>
> But Lychee checks links on a page and tells you which ones are broken. It doesn't tell you how many pages contain each broken link. It doesn't classify issues by priority. It doesn't generate stakeholder reports. It doesn't support webhook notifications. And it doesn't support cookie-based session auth for staging environments.
>
> LinkCanary is slower on raw speed. But it's built for the full workflow:
> → Crawl → classify → prioritize → export → notify → repeat.
>
> If you're running a static site with 10 pages, Lychee is probably fine. If you're managing a 2,000-page documentation site with a content team, you need more than a list of broken URLs.
>
> **Hashtags:** #OpenSource #TechnicalSEO #WebDev #DocumentationEngineering

---

**BlueSky (Monday)**
> **Post type:** Behind the build
>
> Why did we build occurrence tracking?
>
> Because the first time we ran a link audit post-migration, we got 400 broken links and no idea where to start.
>
> Sorted by occurrences: the top 8 issues covered ~60% of the broken link appearances. All template-level problems.
>
> That's the 80/20 rule applied to link health. Occurrence tracking makes it automatic.

---

**BlueSky (Wednesday)**
> **Post type:** Open question
>
> When you get a list of broken links from an audit, how do you decide which to fix first?
>
> Genuinely curious what the default workflow looks like for most teams.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> LinkCanary's HTML report is shareable with one command:
>
> ```
> linkcheck --sitemap https://yoursite.com/sitemap.xml --format html --output report.html
> ```
>
> Open `report.html` in a browser. Filter by status, sort by occurrence count, share with your team.
>
> No login required. No SaaS account. Just a file.

---

### Week 4 — Site Migrations & Content Teams

**LinkedIn (Tuesday)**
> **Post type:** Real-world scenario
>
> Title: "What happens to your links when you change CMS?"
>
> Body:
> You've migrated from WordPress to Ghost. Or Squarespace to Webflow. Or custom to Docusaurus.
>
> You've set up redirects. You've tested the homepage, the about page, the pricing page.
>
> But your blog has 800 posts. Each one has internal links to other posts, documentation pages, product pages that may have moved. Some of those links appear in your blog post template — meaning every post inherits the broken link.
>
> This is where site migration audits get expensive. Not in time spent crawling — in time spent triaging.
>
> LinkCanary was built for this exact scenario. Post-migration, run a full sitemap crawl. Sort by occurrence. Fix the template issues first (usually 5–10 broken URLs). Then address the long-tail post-specific broken links.
>
> We also export to MDX format natively — useful if you're migrating to Ghost or a Markdown-based CMS.
>
> **Hashtags:** #SiteMigration #ContentOps #SEO #WebDev #CMS

---

**LinkedIn (Thursday)**
> **Post type:** Feature spotlight — export formats
>
> Title: "One audit. Six export formats. Every stakeholder covered."
>
> Body:
> A link audit means different things to different people:
>
> → Developer: needs CSV or JSON to pipe into a script
> → Content manager: needs Excel with filtering
> → Client: needs a branded PDF or interactive HTML report
> → SEO lead: wants Google Sheets with live data
> → CMS editor: needs MDX format for Ghost or Docusaurus
>
> LinkCanary exports to all of these from the same crawl:
> `--format csv | json | html | excel | pdf | google-sheets | mdx`
>
> One command. One source of truth. No manual reformatting.
>
> **Hashtags:** #ContentStrategy #SEO #TechnicalSEO #WebDev #Reporting

---

**BlueSky (Monday)**
> **Post type:** Quick comparison
>
> Post-migration checklist that most teams skip:
>
> ❌ "I checked the main pages manually" — misses template-level issues
> ❌ "We set up 301 redirects" — doesn't catch redirect chains or loops
> ❌ "We'll monitor after launch" — by then users have already hit the errors
>
> ✅ Run `linkcheck` against staging before go-live
> ✅ Sort by occurrence count — template issues float to the top
> ✅ Fix before launch, not after

---

**BlueSky (Wednesday)**
> **Post type:** Feature callout
>
> LinkCanary traces full redirect chains, not just the final status:
>
> `301:https://old.com/post → 302:https://redirect.com/landing → 200:https://final.com`
>
> A 3-hop redirect chain hurts page speed and SEO. Most checkers just tell you the final destination is OK. LinkCanary shows you the whole path.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> Working with a CMS on a subdirectory like `/blog`?
>
> ```
> linkcheck --sitemap https://yoursite.com/blog/sitemap.xml \
>   --base-url https://yoursite.com
> ```
>
> LinkCanary handles WordPress/Ghost-style subdirectory installs correctly, including relative URL resolution. No false positives on internal links.

---

## Month 2: Feature Depth & Competitor Contrast
**Theme: "Built for teams that ship continuously"**

Month 2 goes deeper on specific features and draws sharper comparisons to Screaming Frog and Lychee. Target: developers and SEO professionals who are already aware of alternatives.

---

### Week 5 — CI/CD & Automation Workflows

**LinkedIn (Tuesday)**
> **Post type:** Thought leadership
>
> Title: "Link checking should be boring. Here's what I mean."
>
> Body:
> The best infrastructure is the kind you stop thinking about.
>
> You don't think about your test suite until it fails. You don't think about your linter until it catches a bug. That's the point — these tools run automatically and only surface when something's wrong.
>
> Link checking has never worked this way. It's been a quarterly manual task. Someone opens Screaming Frog, runs a crawl, exports a CSV, files a ticket, forgets about it.
>
> LinkCanary's GitHub Action changes the model. Add it to your CI pipeline once. From then on, broken links are caught on every PR — automatically, silently, until they're not.
>
> Boring infrastructure. That's the goal.
>
> **Hashtags:** #DevOps #CI #WebDev #SEO #OpenSource

---

**LinkedIn (Thursday)**
> **Post type:** Technical showcase — Docker + scheduled crawls
>
> Title: "Scheduled link monitoring with Docker Compose (5-minute setup)"
>
> Body:
> LinkCanary ships a Docker image, which means you can run scheduled crawls in any environment that supports containers.
>
> Here's a basic Docker Compose setup that crawls your sitemap nightly and saves the report:
>
> ```yaml
> services:
>   linkcanary:
>     image: linkcanary/linkcanary
>     command: >
>       linkcheck --sitemap https://yoursite.com/sitemap.xml
>       --format html --output /reports/nightly.html
>     volumes:
>       - ./reports:/reports
>     environment:
>       - WEBHOOK_URL=${SLACK_WEBHOOK}
> ```
>
> Add a cron job, a Kubernetes CronJob, or a GitHub Actions schedule trigger — you've got continuous link monitoring with zero manual overhead.
>
> Full docs: [link to repo]
>
> **Hashtags:** #Docker #DevOps #WebDev #SEO #OpenSource

---

**BlueSky (Monday)**
> **Post type:** Comparison thread
>
> 1/ A direct comparison of how Screaming Frog and LinkCanary handle a common workflow: "run a link audit in CI on every deploy."
>
> 2/ Screaming Frog:
> - Desktop app only
> - No CLI
> - No GitHub Action
> - No exit codes
> - Requires manual export after each run
> - License: ~$250/year
>
> 3/ LinkCanary:
> - CLI (`linkcheck`)
> - GitHub Action (native)
> - Docker image
> - Exit code 1 on issues found
> - Reports auto-exported on every run
> - License: MIT (free)
>
> 4/ SF is excellent for deep one-off audits with JS rendering. LC is for continuous, automated, pipeline-integrated checking. Pick the right tool for your workflow.

---

**BlueSky (Wednesday)**
> **Post type:** Quick tip
>
> `--since` flag: only crawl pages modified after a date.
>
> ```
> linkcheck --sitemap https://yoursite.com/sitemap.xml --since 2026-04-01
> ```
>
> Useful for weekly incremental audits on large sites — you only check pages that changed, keeping CI times fast.

---

**BlueSky (Friday)**
> **Post type:** Feature callout
>
> LinkCanary distinguishes real 503s from temporary ones.
>
> Smart retry with exponential backoff: if a URL returns 502/503/504, LC retries with increasing delays before flagging it as broken.
>
> No more false positives from flaky hosting during a crawl. Only real broken links reach your report.

---

### Week 6 — Staging & Auth Environments

**LinkedIn (Tuesday)**
> **Post type:** Feature spotlight — authentication support
>
> Title: "Audit your staging environment, not just production."
>
> Body:
> The right time to catch broken links is before launch — on staging. But staging environments are usually protected.
>
> LinkCanary supports three authentication methods out of the box:
>
> **Basic Auth:**
> `linkcheck --sitemap https://staging.yoursite.com/sitemap.xml --auth-username user --auth-password pass`
>
> **Bearer token:**
> `linkcheck --sitemap ... --auth-header "Authorization: Bearer <token>"`
>
> **Cookie session:**
> `linkcheck --sitemap ... --cookie "session=abc123; csrftoken=xyz"`
>
> Add your credentials as CI secrets and your staging audit runs automatically on every PR — authenticated, private, fully automated.
>
> No tool I know of covers all three auth methods. Screaming Frog supports Basic Auth only (via its UI). Lychee has no built-in auth.
>
> **Hashtags:** #DevOps #CI #Staging #WebDev #TechnicalSEO

---

**LinkedIn (Thursday)**
> **Post type:** Scenario / agency use case
>
> Title: "How agencies can automate client link reports."
>
> Body:
> Client deliverables shouldn't require you to manually run Screaming Frog and format a report every week.
>
> Here's an agency workflow using LinkCanary:
>
> 1. Schedule a weekly crawl via GitHub Actions or a cron job
> 2. Export to PDF (`--format pdf`) for the client-facing report
> 3. Export to Google Sheets (`--format google-sheets`) for live tracking
> 4. Send a webhook notification to Slack or Teams with the summary
>
> The entire workflow runs automatically. The client gets a weekly report. You get an alert only when issues are found.
>
> No manual exports. No "did anyone run the audit this week?"
>
> **Hashtags:** #AgencyLife #ContentStrategy #SEO #WebDev #Automation

---

**BlueSky (Monday)**
> **Post type:** Quick tip
>
> Testing a staging site behind Basic Auth?
>
> ```
> linkcheck \
>   --sitemap https://staging.mysite.com/sitemap.xml \
>   --auth-username $STAGING_USER \
>   --auth-password $STAGING_PASS
> ```
>
> Works in GitHub Actions with secrets. Most link checkers stop here.
>
> LC also supports bearer tokens and cookie sessions for more complex auth setups.

---

**BlueSky (Wednesday)**
> **Post type:** Comparison
>
> Lychee auth support: HTTP Basic Auth only
>
> LinkCanary auth support:
> - Basic Auth ✅
> - Bearer token header ✅
> - Cookie/session auth ✅
> - Custom User-Agent ✅
>
> If your staging environment uses anything other than Basic Auth, Lychee can't audit it. LC can.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> You can test exactly how LinkCanary resolves URLs before running a full crawl:
>
> ```
> linkcheck --test-urls --base-url https://yoursite.com
> ```
>
> Useful for debugging subdirectory setups, `<base>` tags, or relative URL resolution edge cases. Saves you from a 30-minute crawl that produces garbage results.

---

### Week 7 — SEO & Redirect Chains

**LinkedIn (Tuesday)**
> **Post type:** SEO-focused thought leadership
>
> Title: "Redirect chains are silent SEO killers. Here's how to find them."
>
> Body:
> A 301 redirect is fine. A chain of redirects — A→B→C→D — is an SEO problem.
>
> Each hop in a redirect chain:
> - Adds latency for the end user
> - Dilutes PageRank passing
> - Increases crawl budget waste for search engines
>
> Most link checkers tell you only the final HTTP status. They see the chain A→D→200 OK and call it clean.
>
> LinkCanary traces the full path. Every hop is logged. Chains are flagged by priority. You can see exactly where the unnecessary redirects are accumulating.
>
> After a site migration, you often end up with chains like: old CMS URL → redirect middleware → new CMS slug → canonical URL. Each step was added incrementally. None of them were cleaned up. LinkCanary makes them visible all at once.
>
> **Hashtags:** #TechnicalSEO #SEO #SiteMigration #WebDev #PageSpeed

---

**LinkedIn (Thursday)**
> **Post type:** Feature spotlight — priority classification
>
> Title: "Not all broken links are equal. Here's how LinkCanary classifies them."
>
> Body:
> LinkCanary assigns a priority to every issue:
>
> **Critical** — 5xx server errors (the page is actively broken or the server is failing)
> **High** — 4xx errors (page genuinely doesn't exist, pure broken link)
> **Medium** — Redirect chains (3+ hops), redirect loops
> **Low** — Canonical mismatches, minor redirect issues
>
> Each issue also includes an actionable recommendation — not just "this is broken" but "update this link to point directly to the canonical URL" or "remove intermediate redirect on /old-blog/".
>
> The combination of priority + occurrence count means you get a true triage order, not just a flat list.
>
> **Hashtags:** #TechnicalSEO #SEO #ContentOps #WebDev

---

**BlueSky (Monday)**
> **Post type:** Quick fact
>
> A redirect chain looks fine in your browser (you end up at the right page) but costs you on:
>
> - Page load time
> - Crawl budget
> - Link equity passing
>
> LinkCanary traces every hop:
> `301:/old → 302:/redirect → 301:/newer → 200:/canonical`
>
> And flags it so you can collapse the chain.

---

**BlueSky (Wednesday)**
> **Post type:** Feature callout
>
> LinkCanary detects redirect loops — where URLs redirect to each other in a cycle.
>
> These are completely invisible to a user (browser breaks the loop) but will crash a naïve crawler and tank your SEO.
>
> LC detects and reports them without getting stuck.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> Want to audit only a section of your site?
>
> ```
> linkcheck --sitemap https://yoursite.com/sitemap.xml \
>   --include "/docs/*"
> ```
>
> `--include` and `--exclude` accept glob or regex patterns. Scope your crawl to exactly what changed.

---

### Week 8 — Web UI & Non-Technical Users

**LinkedIn (Tuesday)**
> **Post type:** Product showcase — Web UI
>
> Title: "Not everyone on your team wants to use a CLI."
>
> Body:
> LinkCanary ships a full web dashboard — React frontend, real-time progress streaming, reports library.
>
> For non-technical users, the workflow is:
> 1. Open the dashboard
> 2. Enter your sitemap URL
> 3. Configure options via the UI (auth, export formats, filters)
> 4. Watch the crawl progress in real-time
> 5. Browse the interactive report or download the format you need
>
> For CI/CD pipelines, use the CLI or GitHub Action directly. The same engine powers both.
>
> The web UI is self-hosted — runs alongside the CLI using Docker Compose. No SaaS subscription, no data leaving your infrastructure.
>
> **Hashtags:** #WebDev #ContentOps #TechnicalSEO #SEO #OpenSource

---

**LinkedIn (Thursday)**
> **Post type:** Comparison — total cost of ownership
>
> Title: "The real cost of your current link checker."
>
> Body:
> Screaming Frog: ~$250/year per user. Desktop only. Manual workflow. Each team member needs their own license.
>
> Lychee: Free, open-source. But raw speed with no workflow integrations. Each stakeholder needs a developer to interpret the output.
>
> LinkCanary: MIT licensed. Self-hosted. CLI, GitHub Action, Web UI, Docker — all included. Exports to PDF, Excel, Google Sheets, HTML for every stakeholder type.
>
> The cost difference isn't just licensing. It's the hours your team spends manually running audits, formatting reports, and triaging undifferentiated lists of broken URLs.
>
> **Hashtags:** #OpenSource #SEO #ContentOps #DevOps #WebDev

---

**BlueSky (Monday)**
> **Post type:** Feature callout
>
> LinkCanary Web UI runs on FastAPI + React 19 and streams crawl progress in real-time via WebSocket.
>
> You can watch pages get checked as they're processed, see issues accumulate, and filter results before the crawl even finishes.
>
> Self-hosted. No telemetry.

---

**BlueSky (Wednesday)**
> **Post type:** Open question
>
> If you self-host tooling for your team, what's the thing you most want from a web UI for a link checker?
>
> - Scheduled crawls
> - Slack/webhook notifications
> - Multi-site management
> - Historical comparison (drift detection)
>
> Building the roadmap, not a trick question.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> The Web UI report library lets you search and filter past crawls.
>
> Useful for: "did this specific broken link exist last month?" or "is the number of redirect chains trending up or down?"
>
> Same HTML reports the CLI generates — stored and browsable in the dashboard.

---

## Month 3: Community, Proof, and Positioning
**Theme: "The infrastructure your content pipeline is missing"**

Month 3 builds social proof, surfaces real-world use cases, and positions LinkCanary as the default choice for teams that care about continuous link health — not just periodic audits.

---

### Week 9 — Use Cases & Workflows by Role

**LinkedIn (Tuesday)**
> **Post type:** Role-based use case — Developer
>
> Title: "How a backend developer uses LinkCanary without thinking about it."
>
> Body:
> Here's how LinkCanary fits into a developer's workflow without adding cognitive overhead:
>
> 1. Add the GitHub Action to `.github/workflows/`
> 2. Point it at the staging sitemap URL
> 3. Add staging credentials as repository secrets
>
> That's it. From now on:
> - Every PR that touches content or templates runs a link audit
> - Broken links fail the CI check and block merge
> - The developer gets a clear diff: "these 3 links were broken by this PR"
>
> It's the same pattern as linting or unit tests. The tool runs automatically. You only think about it when something breaks.
>
> **Hashtags:** #WebDev #DevOps #CI #GitHub #OpenSource

---

**LinkedIn (Thursday)**
> **Post type:** Role-based use case — SEO Professional
>
> Title: "LinkCanary for technical SEO: what it catches that Screaming Frog misses in your workflow."
>
> Body:
> Let me be precise: Screaming Frog is a better SEO crawler than LinkCanary. It renders JavaScript. It analyzes hreflang. It does log file analysis. For deep site audits, it's the professional standard.
>
> But there's a gap in the Screaming Frog workflow: automation.
>
> You can't schedule SF to run on a deploy trigger. You can't get a Slack alert when a new broken link appears. You can't fail a PR build. You run it manually, on a schedule you set yourself, and the window between audits is full of risk.
>
> LinkCanary fills the automation gap. Run it in CI. Get webhook alerts to Slack. Export to Google Sheets for ongoing tracking. Schedule nightly crawls.
>
> Use SF for deep quarterly audits. Use LinkCanary for continuous monitoring in between.
>
> **Hashtags:** #TechnicalSEO #SEO #WebDev #Automation #ContentStrategy

---

**BlueSky (Monday)**
> **Post type:** Use case thread
>
> 1/ Three workflows where LinkCanary beats both Screaming Frog and Lychee:
>
> 2/ PR checks: You have a staging environment. You want to block merge if new broken links are introduced. SF can't do it (no CLI). Lychee can do it but gives no occurrence data. LC does both.
>
> 3/ Post-migration triage: You have 500 broken links after a CMS migration. SF gives you a flat list. Lychee gives you a flat list. LC gives you a list sorted by occurrence count — fix the top 10 and clear 70% of issues.
>
> 4/ Stakeholder reporting: Developer gets CSV/JSON. Content manager gets Excel. Client gets PDF. All from one crawl. SF requires manual export formatting. Lychee has no reports.

---

**BlueSky (Wednesday)**
> **Post type:** Quick callout
>
> robots.txt compliance: LinkCanary respects it by default.
>
> If you're auditing a site you don't own (allowed with permission, obviously), use `--ignore-robots-txt` to bypass.
>
> Most internal auditing tools get this wrong. LC gets it right out of the box.

---

**BlueSky (Friday)**
> **Post type:** Quick tip
>
> Google Sheets export for live tracking:
>
> ```
> linkcheck --sitemap https://yoursite.com/sitemap.xml \
>   --format google-sheets \
>   --sheets-id YOUR_SHEET_ID
> ```
>
> Each crawl appends a new sheet with a timestamp. You get a historical record of link health over time — shareable with your team, always up to date.

---

### Week 10 — Community & Open Source

**LinkedIn (Tuesday)**
> **Post type:** Behind the build / open source values
>
> Title: "Why we made LinkCanary MIT licensed and self-hosted."
>
> Body:
> There's a version of LinkCanary that could have been a SaaS product. Charge per URL. Upsell reports. Add a dashboard with a monthly subscription.
>
> We chose not to do that. Here's why.
>
> The teams that most need continuous link monitoring — agencies, docs teams, small engineering teams — are often the ones least able to justify another SaaS line item. And the data flowing through a link audit (staging URLs, auth credentials, internal content structure) is exactly the kind of thing you shouldn't want leaving your infrastructure.
>
> MIT license means you can fork it, extend it, integrate it, and ship it without asking permission. Self-hosted means your credentials and crawl data stay in your environment.
>
> We think the right business model for infrastructure tooling is open core, not SaaS extraction.
>
> **Hashtags:** #OpenSource #WebDev #DevOps #SEO #BuildInPublic

---

**LinkedIn (Thursday)**
> **Post type:** Feature spotlight — MCP integration
>
> Title: "LinkCanary now speaks MCP."
>
> Body:
> The Model Context Protocol is emerging as a standard for connecting AI assistants to tools and data sources.
>
> LinkCanary's MCP integration means you can query your link audit data from any MCP-compatible AI assistant. Ask questions like:
>
> "What are the 5 highest-occurrence broken links from last week's crawl?"
> "Which pages have redirect chains longer than 2 hops?"
> "Have any new 4xx errors appeared since the last crawl?"
>
> Instead of opening a report and manually filtering, you get answers in natural language, backed by real crawl data.
>
> This is where tooling goes next: not just structured reports, but queryable data surfaces that AI can reason over.
>
> **Hashtags:** #AI #MCP #WebDev #SEO #OpenSource #BuildInPublic

---

**BlueSky (Monday)**
> **Post type:** Contribution callout
>
> LinkCanary is MIT licensed and has issues tagged `good first issue` for anyone who wants to contribute.
>
> Things we'd love help with:
> - Additional export format adapters
> - Additional auth method support
> - Improved JavaScript-rendered page support
>
> The codebase is Python + FastAPI + React. PRs welcome.
>
> [repo link]

---

**BlueSky (Wednesday)**
> **Post type:** Feature callout — MCP
>
> LinkCanary has MCP (Model Context Protocol) integration.
>
> Connect it to Claude, Cursor, or any MCP-compatible assistant and query your crawl results in natural language.
>
> "Show me all broken links introduced in the last 7 days" hits different when you can just ask for it.

---

**BlueSky (Friday)**
> **Post type:** Retrospective / reflection
>
> 3 months ago this project started because Screaming Frog couldn't run in CI and Lychee didn't tell us where broken links appeared.
>
> What we didn't expect to build: staging auth, Google Sheets export, MCP integration, Docker support, a web UI with real-time WebSocket progress.
>
> What was always the point: occurrence tracking. Still the feature that surprises people most.

---

### Week 11 — Competitive Positioning Final Push

**LinkedIn (Tuesday)**
> **Post type:** Summary comparison — full landscape
>
> Title: "Screaming Frog vs Lychee vs LinkCanary: choosing the right tool."
>
> Body:
> These three tools solve the same surface problem (broken links) with completely different philosophies. Here's the honest comparison:
>
> **Screaming Frog SEO Spider**
> Best for: Deep one-off SEO audits, JavaScript-rendered sites, desktop workflows
> Limitations: Desktop-only, no CI/CD, manual exports, $250/year/user
>
> **Lychee**
> Best for: Fast raw checks on large sites, simple CI integration, Rust performance
> Limitations: No occurrence data, no workflow integrations, no reports, no staging auth
>
> **LinkCanary**
> Best for: Continuous automated monitoring, post-migration triage, team reporting, staging environments
> Limitations: No JavaScript rendering, slower than Lychee on raw speed
>
> Our honest recommendation: use Screaming Frog for deep quarterly SEO audits. Add LinkCanary for continuous CI/CD monitoring. Replace Lychee with LinkCanary if you need more than a list of broken URLs.
>
> **Hashtags:** #TechnicalSEO #SEO #WebDev #OpenSource #ContentStrategy

---

**LinkedIn (Thursday)**
> **Post type:** Thought leadership / final positioning
>
> Title: "The difference between an audit tool and infrastructure."
>
> Body:
> An audit tool is something you run.
> Infrastructure is something that runs for you.
>
> Screaming Frog is an audit tool. It's excellent at what it does. But it requires a human to open it, configure a crawl, wait for it to finish, export the results, and distribute them. Every time.
>
> LinkCanary is infrastructure. You configure it once. It runs on every deploy, every night, every PR. It alerts you when something breaks. It exports reports automatically. You stop thinking about it until a link breaks — and then you know immediately.
>
> The question isn't "which tool finds more broken links?" It's "which model fits the way your team actually ships software?"
>
> If you ship continuously, your link checking should too.
>
> **Hashtags:** #DevOps #WebDev #SEO #ContentOps #OpenSource #BuildInPublic

---

**BlueSky (Monday)**
> **Post type:** Summary thread
>
> 1/ After 3 months of posts about LinkCanary, here's the one-paragraph version:
>
> 2/ LinkCanary is an open-source link auditor that does one thing no other tool does: tracks how many pages each broken link appears on. Sort by occurrence count. Fix the top 10 issues. Clear 70% of your problem.
>
> 3/ It runs in CI/CD (GitHub Action, Docker), exports to 6+ formats, supports staging auth (Basic, Bearer, Cookie), traces full redirect chains, and has a self-hosted web UI.
>
> 4/ MIT licensed. Free. No SaaS pricing. Your data stays on your infrastructure.
>
> github: [repo link]

---

**BlueSky (Wednesday)**
> **Post type:** Open question / engagement
>
> What's the one feature that would make you switch from your current link checker?
>
> Curious what the community actually wants — not what we think they want.

---

**BlueSky (Friday)**
> **Post type:** Thank you / community
>
> Thanks to everyone who tested, filed issues, sent PRs, or just starred the repo.
>
> Open source is the only reason a small tool can go from "we had this annoying problem" to "actually useful infrastructure" in a few months.
>
> More coming. Next up: incremental diff reports and JS rendering support.

---

### Week 12 — Momentum & Conversion

**LinkedIn (Tuesday)**
> **Post type:** Case study format
>
> Title: "From 400 broken links to a 10-item fix list: a migration story."
>
> Body:
> Scenario: a 2,000-page documentation site migrates from a custom CMS to Docusaurus. 3 weeks after launch, a routine check turns up 400 broken links.
>
> With a flat list from a traditional checker, this is a 2-week content team project.
>
> With LinkCanary's occurrence tracking:
>
> - Top 10 broken URLs account for 312 of the 400 occurrences
> - 8 of those 10 are in shared template components (sidebar nav, footer, header CTA)
> - Fixing those 8 components clears 78% of broken link occurrences
> - The remaining 92 are post-specific — addressable over the next sprint
>
> Total time to resolve the critical issues: 4 hours instead of 2 weeks.
>
> This is what occurrence tracking does to a broken link triage project.
>
> **Hashtags:** #TechnicalSEO #SiteMigration #ContentOps #WebDev #Documentation

---

**LinkedIn (Thursday)**
> **Post type:** Call to action / final month summary
>
> Title: "If you've read any of these posts and thought 'we have this problem' — here's where to start."
>
> Body:
> Start simple:
>
> ```
> pip install linkcanary
> linkcheck --sitemap https://yoursite.com/sitemap.xml --format html
> ```
>
> Open the HTML report. Look at the occurrence column. The highest numbers tell you exactly what to fix first.
>
> If you want CI integration, the GitHub Action docs are in the README. If you want the web UI, there's a Docker Compose example in the repo. If you want to send weekly reports to Google Sheets, there's a flag for that too.
>
> Everything is MIT licensed, self-hosted, and documented.
>
> Pull requests and issues welcome.
>
> [repo link]
>
> **Hashtags:** #OpenSource #WebDev #SEO #TechnicalSEO #DevOps #ContentOps

---

**BlueSky (Monday)**
> **Post type:** Final tip
>
> If you take nothing else from these posts:
>
> ```
> pip install linkcanary
> linkcheck --sitemap https://yoursite.com/sitemap.xml
> ```
>
> Sort by occurrences. Fix the top 10 URLs. You'll clear most of your broken link problem in an afternoon.
>
> That's it. That's the pitch.

---

**BlueSky (Wednesday)**
> **Post type:** Forward look
>
> Next big things on the LinkCanary roadmap:
>
> - Incremental diff reports: "what broke since last crawl?"
> - JavaScript rendering support (for SPAs)
> - Historical trend charts in the web UI
>
> What else would make this useful for you?

---

**BlueSky (Friday)**
> **Post type:** Evergreen close
>
> LinkCanary exists because:
>
> - Screaming Frog doesn't run in CI
> - Lychee doesn't track occurrences
> - No tool told us *where* broken links appeared
>
> MIT. Self-hosted. Open source.
>
> github: [repo link]

---

## Content Calendar Summary

### LinkedIn (24 posts over 12 weeks)

| Week | Tuesday | Thursday |
|---|---|---|
| 1 | Launch / origin story | — |
| 2 | Manual audit problem | GitHub Actions integration |
| 3 | Occurrence tracking | Lychee comparison |
| 4 | Site migration scenario | Export formats |
| 5 | Boring infrastructure thesis | Docker + scheduled crawls |
| 6 | Staging auth support | Agency reporting workflow |
| 7 | Redirect chains + SEO | Priority classification |
| 8 | Web UI showcase | Total cost comparison |
| 9 | Developer use case | SEO professional use case |
| 10 | Open source values | MCP integration |
| 11 | Full landscape comparison | Audit vs infrastructure |
| 12 | Case study | Final CTA + getting started |

### BlueSky (≈40 posts over 12 weeks)

| Week | Mon | Wed | Fri |
|---|---|---|---|
| 1 | Intro thread | Open question (poll) | Quick start tip |
| 2 | Migration scenario | SF vs LC in CI | URL file flag tip |
| 3 | Behind occurrence tracking | Open question (triage) | HTML report tip |
| 4 | Migration checklist | Redirect chain tracing | Subdirectory tip |
| 5 | SF vs LC comparison thread | `--since` flag tip | Retry logic callout |
| 6 | Staging auth tip | Lychee auth comparison | `--test-urls` tip |
| 7 | Redirect chain fact | Redirect loop detection | `--include` tip |
| 8 | Web UI callout | Open question (roadmap) | Reports library tip |
| 9 | 3-workflow comparison | robots.txt callout | Google Sheets tip |
| 10 | Contribution callout | MCP callout | Retrospective |
| 11 | Summary thread | Final open question | Thank you post |
| 12 | Final quick start | Roadmap forward look | Evergreen close |

---

## Hashtag Strategy

### LinkedIn Core Tags (rotate, max 5 per post)
`#WebDev` `#SEO` `#TechnicalSEO` `#DevOps` `#OpenSource` `#ContentOps` `#CI` `#SiteMigration` `#ContentStrategy` `#BuildInPublic`

### BlueSky
BlueSky hashtags have lower algorithmic weight than LinkedIn. Use 1–2 max, focus on `#webdev` `#seo` `#opensource` `#devtools`. Engagement comes more from replies and reposts than hashtag discovery.

---

## Engagement Playbook

### LinkedIn
- Reply to every comment within 24 hours
- Share posts in relevant LinkedIn groups: "SEO professionals," "Web Developers," "DevOps practitioners"
- Tag relevant communities or individuals when directly relevant (not spammy)
- Boost top-performing posts with a small budget if organic reach plateaus

### BlueSky
- Thread format outperforms single posts for technical content
- Ask questions; the dev community on Bluesky is conversational
- Share when others post about broken links, site migrations, or Screaming Frog — engage authentically
- Cross-post to relevant starter packs (#devtools, #webdev, #opensourcesoftware)

---

## Success Metrics (3-month targets)

| Metric | Platform | Target |
|---|---|---|
| Impressions | LinkedIn | 50,000+ |
| Engagement rate | LinkedIn | 3%+ |
| Profile link clicks | LinkedIn | 500+ |
| Followers gained | LinkedIn | 200+ |
| GitHub referral traffic from LinkedIn | — | 150+ clicks |
| Impressions | BlueSky | 30,000+ |
| Replies / reposts | BlueSky | 200+ |
| GitHub referral traffic from BlueSky | — | 200+ clicks |
| GitHub stars (3-month growth) | — | +500 |
