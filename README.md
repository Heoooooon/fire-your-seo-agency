# 🔥 fire-your-seo-agency

[한국어](./README.ko.md) · **English**

[![GitHub stars](https://img.shields.io/github/stars/leopard627/fire-your-seo-agency?style=flat&logo=github)](https://github.com/leopard627/fire-your-seo-agency/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/leopard627/fire-your-seo-agency?style=flat&logo=github)](https://github.com/leopard627/fire-your-seo-agency/fork)
[![Latest release](https://img.shields.io/github/v/release/leopard627/fire-your-seo-agency?style=flat&label=release)](https://github.com/leopard627/fire-your-seo-agency/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat)](./LICENSE)

![fire-your-seo-agency](./assets/social-preview.png)

> **Paying $400–$2,500/month for an SEO or "AI visibility" agency? Fire them. Your AI agent can do the work.**

A wave of services now charges monthly retainers for "AI-era search optimization",
"guaranteed ChatGPT citations", and "LLM visibility". Most of what they actually do is
**public standards and repeatable checklists**. When a human does it, it's a retainer.
When your agent does it, it's a skill.

This fork packages [leopard627's original MIT skill](https://github.com/leopard627/fire-your-seo-agency)
for **OmO/Senpi**, while retaining the [Claude Code](https://claude.com/claude-code)
entry point. The audit playbook and references are credited to leopard627; this fork
adds the package manifest, Korean-first OmO entry point and package validation.

## Built on real numbers

This is not theory. The same playbook, applied to [Chickenstock](https://www.chickstockfi.com) — a solo-built Korean stock research service:

- **1.54M search impressions in 30 days** (+85,578% MoM), 7.4K clicks
- Pages **cited paragraph-by-paragraph by Naver's AI Briefing** (Korea's answer engine)
- Zero ad spend — all inbound from search and AI citations

The journey is documented publicly on [Threads @kindainvestor](https://www.threads.com/@kindainvestor).

## The five lanes

"Search optimization" means different things to different engines. This skill treats them
as five distinct lanes:

| Lane | Target | The question it answers |
|---|---|---|
| **SEO** | Google & Bing crawlers | Can crawlers read and index my content at all? |
| **AEO** (Answer Engine) | Google AI Overviews, Bing Copilot | Does the AI answer box above the results cite me? |
| **GEO** (Generative Engine) | ChatGPT, Perplexity, Claude | When generative AI browses, am I the primary source? |
| **LLMO** (LLM Optimization) | The model's own knowledge | Does the model know my brand — and know it correctly? |
| **NEO** (Naver Engine) | Naver search & AI Briefing | Half of the Korean market — does Naver cite me? |

**NEO is what makes this skill different.** Global AEO guides ignore Naver entirely,
but if you serve the Korean market, half your traffic lives there.

**Plus a content engine.** Most of a retainer pays for "N posts a month". This skill
replaces that with a pipeline: a question backlog pulled from your own search data, a
frontmatter content model that generates the JSON-LD, a publish gate every post must pass,
and a refresh/merge policy so posts don't rot. Output is measured as "posts that get seen
and cited", not "posts published".

## Install

### OmO / Senpi

Add this entry to the existing `packages` array in `~/.omo/agent/settings.json`.
The PR is not merged, so use its branch:

```json
"packages": ["git:github.com/Heoooooon/fire-your-seo-agency@omo-package"]
```

After a future merge, the default-branch entry is
`git:github.com/Heoooooon/fire-your-seo-agency`. Start a new session or `/reload`.
This package registers only `skills/fire-your-seo-agency` through `pi.skills`.
It has no npm dependencies or install hooks and does not change your settings itself.

Ask naturally, for example:

```text
이 병원 홈페이지 SEO와 네이버 서치어드바이저·플레이스·AI 브리핑 노출을 진단해줘.
이 앱 랜딩의 검색 노출과 ChatGPT 인용 가능성을 점검하고 llms.txt 개선안을 만들어줘.
```

See [우리 사이트에 쓰는 법](./skills/fire-your-seo-agency/SKILL.md#우리-사이트에-쓰는-법)
for generic clinic and app examples. Audit-only requests remain read-only; local
implementation and external submissions follow the scope the user authorized.

### Claude Code (existing installation)

The original root `SKILL.md`, `references/` and `.claude-plugin/` remain in place.
For this fork as a plugin:

```
/plugin marketplace add Heoooooon/fire-your-seo-agency
/plugin install fire-your-seo-agency@fire-your-seo-agency
```

Or via git clone:

```bash
# As a project skill (this project only)
git clone https://github.com/Heoooooon/fire-your-seo-agency.git .claude/skills/fire-your-seo-agency

# Or as a personal skill (every project)
git clone https://github.com/Heoooooon/fire-your-seo-agency.git ~/.claude/skills/fire-your-seo-agency
```

Then in Claude Code:

```
/fire-your-seo-agency audit my site
```

Your agent starts with a crawler-eye audit and returns a scorecard like this before
touching anything:

| Lane | Status | Evidence |
|---|---|---|
| SEO | ⚠️ | Body is SSR'd, but 214 detail pages missing from sitemap |
| AEO | ❌ | No direct-answer first paragraphs; FAQ structured data: 0 |
| GEO | ❌ | No llms.txt; GPTBot/PerplexityBot policy undecided in robots.txt |
| LLMO | ⚠️ | Brand name spelled 3 different ways across surfaces |
| NEO | ❌ | Not registered in Naver Search Advisor |

…then proposes priorities, implements them, and schedules the re-measurement.

## What it does

1. **Audit** — reads your site the way a crawler does (no JavaScript) and scores all five lanes
2. **Technical base** — fixes SSR exposure, sitemaps, meta, structured data
3. **Intent landing pages** — designs pages on the "one question = one page" principle
4. **Machine readability** — llms.txt, JSON-LD, citation-ready paragraph structure
5. **Naver** — from Search Advisor registration to AI Briefing citation requirements
6. **Content engine** — sub-blog setup, question backlog, publish gate, refresh & merge policy
7. **Measurement loop** — schedules a re-measurement and proves the change with numbers

## What it refuses to do

- ❌ Buying backlinks, engagement pods, content spam — **we don't fight the search engine**
- ❌ "Guaranteed rankings" promises — no claims without measurement
- ❌ Keyword stuffing, hidden text, cloaking — nothing that gets your domain killed

The whole philosophy fits in one line: **AI doesn't cite good writing. AI cites accurate data.**
Become the primary source for a number, and the citations follow.

## Structure

```
package.json          ← OmO package manifest (pi.skills)
skills/fire-your-seo-agency/
  SKILL.md            ← Korean-first OmO/Senpi entry point
scripts/verify.mjs    ← actual Senpi loader check (no settings writes)
SKILL.md              ← agent operating procedure (audit → implement → measure)
references/
  seo.md              ← technical SEO checklist + real-world traps
  aeo.md              ← answer engine optimization (Bing WMT · AI Overviews · Copilot · E-E-A-T)
  geo.md              ← generative engine optimization (AI crawler policy · llms.txt · primary source)
  llmo.md             ← model-knowledge optimization (brand entity)
  neo-naver.md        ← Naver (Search Advisor · AI Briefing · blog two-track)
  content.md          ← content ops (sub-blog · content model · backlog · publish gate · refresh)
  measure.md          ← the measurement loop (fixing it is not the finish line)
  en/                 ← English mirrors of all reference docs (for human readers)
.claude-plugin/       ← plugin & marketplace manifests (/plugin install support)
tools/                ← repository checks (validate.py) + lossless asset optimizer
tests/                ← unit tests for the checks
.github/workflows/    ← CI: checks, tests and the asset check on every push/PR
```

> The Korean documents under `references/` are canonical (the agent reads those);
> `references/en/` mirrors them in English for human readers.
> The OmO entry point resolves shared references as `../../references/` from its
> own directory; references were not moved, preserving Claude clone install paths.

## Repository checks

This repo checks itself — `.github/workflows/validate.yml` runs the Python checks on
every push and pull request. The Senpi loader check is local and needs Senpi installed:

```bash
python3 tools/validate.py --strict          # 12 checks, standard library only
python3 -m unittest discover -s tests -t .  # unit tests for every check
python3 -m pip install pillow
python3 tools/optimize_assets.py --check    # flags recompressible assets
node scripts/verify.mjs                    # needs a locally installed Senpi
```

Package aliases: `npm test`, `npm run validate`, `npm run verify` (or `bun run`).
The loader check defaults to `~/.bun/install/global/node_modules/@code-yeongyu/senpi`;
set `SENPI_ROOT` to another Senpi installation directory if needed.

`tools/validate.py` enforces the things that rot silently in a docs-only repo: the
`SKILL.md` frontmatter contract (kebab-case name, 64-character name limit, 1024-character
single-line description), `plugin.json` ↔ `marketplace.json` version and name agreement,
the OmO skill frontmatter and `package.json` registration/version/license agreement,
`CHANGELOG.md` matching the manifest version, relative links and anchors, Korean/English
reference parity (heading counts, table rows, checkboxes, section numbering), the asset
budget and preview dimensions, the MIT license metadata, and a secret scan over every
text file.

## Star History

<a href="https://www.star-history.com/#leopard627/fire-your-seo-agency&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=leopard627/fire-your-seo-agency&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=leopard627/fire-your-seo-agency&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=leopard627/fire-your-seo-agency&type=Date" />
  </picture>
</a>

## License

MIT. Original skill, audit methodology and reference documents by
[leopard627](https://github.com/leopard627/fire-your-seo-agency).
The original `Copyright (c) 2026 leopard627` notice is preserved in [LICENSE](./LICENSE).
OmO/Senpi packaging is maintained in [this fork](https://github.com/Heoooooon/fire-your-seo-agency).
