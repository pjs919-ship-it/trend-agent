---
name: brand-naming
description: >-
  Metaphor-driven product, brand, and SaaS naming workflow (adapted and
  localized from glacierphonk/naming, arnabbagxd/Brand-building-skills, and
  founder-skill). Use whenever the user asks to name or rename a product,
  brand, feature, or SaaS, asks for name candidates, or asks to evaluate
  existing brand names against anti-patterns and real availability.
---

# Brand Naming Strategist

Creates memorable, distinctive names rooted in **concrete metaphor rather than thesaurus synonyms or `Category + Modifier` AI slop**. The name carries recall and emotion; the tagline/subtitle carries explanation.

## 1. Naming Brief (Ask Only What Is Missing)
Gather or extract from project context before generating any name:
1. **Core function (1 sentence)**: What does it actually do for whom? (Strip features down to the core verb.)
2. **Target audience & market**: Who says it out loud, and in which languages?
3. **Character / Taste**: 2–3 reference brands the user admires + tone sliders (warm vs sharp, editorial vs technical, playful vs serious).
4. **Architecture & Subtitle Pairing**: Standalone vs family? If a descriptive subtitle already exists, ban repeating those words in the name.
5. **Hard Bans**: Words, suffixes, or styles explicitly rejected by the user.
6. **Priority Channels**: Exact `.com`/`.kr` domain, KIPRIS trademark class, Instagram/YouTube handles, SEO search clarity.

## 2. Metaphor Exploration (Before Generating Names)
Never open a thesaurus for "trend", "beauty", or "AI". Map conceptual territories from *"What else in the world does this core job?"*:
- **Physical world / Craft**: Observatory, lens, loom, blueprint, studio, atelier, folio, index, edit.
- **Nature / Sensory**: Current, tide, grain, hue, luster, 결(texture/grain).
- **Profession / Role**: Curator, scout, herald, editor, strategist, 안목(discernment).
- **Cross-pollinate**: Blend an unexpected domain (e.g., editorial magazine or film set *cue*) with the product's daily ritual.

Select **2–4 distinct territories** spanning different styles (e.g., *short evocative English*, *1–2 syllable Korean editorial word*, *grounded invented coinage*).

## 3. Generate & Prune Internally (Steps 3–4 Stay Hidden)
Generate 30+ raw candidates internally across territories, then cut ruthlessly using [references/anti-patterns-and-rubric.md](./references/anti-patterns-and-rubric.md):
- **Kill AI Slop & Konglish Compounds**: Reject `~핏`, `~앵글`, `~레이더`, `~랩`, `~허브`, `~싱크`, `AI~`, `Smart~`, `-ly`, `-ify`, `-ora`, `-ix`.
- **Compound Test**: Cover half the word; if either half is generic filler or swappable with a synonym, delete it.
- **Semantic Self-Contradiction Check**: Check all common meanings, idioms, and slang in Korean and English so no secondary meaning undermines trust.
- **Phone Test & Length**: Prefer 1–2 syllables (max 3), ≤ 6–7 letters, immediately spellable after hearing it once in a café or meeting.

## 4. Mandatory Availability Gate (Real Checks Only)
Never recommend a finalist from memory. Run `search_web` on every surviving finalist in priority order:
1. **Direct competitor / SaaS collision first**: `"[name]" 뷰티 OR 마케팅 OR SaaS` — if a direct competitor or major agency owns it, drop immediately.
2. **Negative slang / unintended association**: Check English + Korean urban/SNS usage (e.g., awkward acronyms).
3. **Korean trademark & searchability**: Note exact KIPRIS / Naver search competition (`"[name]" 상표` or major brand noise) and realistic domain options (`.kr`, `.com`, `get~`, etc.). State plainly that public web checks are preliminary, not legal trademark advice.

## 5. Score & Present Finalists (Top 3–5 Only)
Score survivors on the 110-pt rubric and contextual sentence tests in [references/anti-patterns-and-rubric.md](./references/anti-patterns-and-rubric.md) (`"오늘 [name]에서 확인해봐"`, `"[name] — [확정 부제]"`).

Present **3–5 vetted finalists** (keep intermediate scratch candidates hidden unless asked):
- **Name** + Metaphor Territory
- **15-second Origin Story ("Why")** — concrete mental image, not a vague vibe
- **Header / Share Preview** paired directly with the product's subtitle
- **Verified Search Status & Honest Tradeoffs** (collisions found, pronunciation/domain caveats)
- Recommend living with the top 2 finalists for 24 hours before locking.

## Iteration Rules
- If the user says candidates feel "tacky/cheesy" (`촌스럽다`), ask for 2–3 admired brands to recalibrate taste and abandon descriptive compounds entirely — switch territories to standalone real words, editorial nouns, or sharp 1-syllable coinages.
