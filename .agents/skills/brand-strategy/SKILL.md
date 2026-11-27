---
name: brand-strategy
description: >-
  Define and maintain core brand strategy, values, vision, mission, competitive
  positioning, manifesto, and centralized brand context (adapted from
  arnabbagxd/Brand-building-skills and marketingskills/product-marketing). Use
  when creating or updating brand values, vision, mission, positioning
  statement, target persona, differentiation, or brand manifesto.
---

# Brand Strategy & Positioning Architect

Establishes sharp, non-generic brand foundations — **origin, what we fight against, vision, mission, behavioral values, and defensible positioning** — and stores them in one canonical context file so visual identity and copywriting stay unified.

*(For naming, use `brand-naming`. For visual tokens/UI colors in this workspace, pair with `brand-identity`. For page headlines and ad copy, hand off to `copywriting`.)*

## Step 1: Canonical Brand Context (Single Source of Truth)
Always check `.agents/brand-context.md` (and existing docs like `docs/POLICY.md` or `README.md`) first:
- **If it exists**: Read it, summarize current version & `Learnings`, and ask only what sections need updating.
- **If missing**: **Auto-draft V1 from the repository/brief** first instead of dumping a 20-question client survey. Ask only 3–5 targeted clarifying questions for genuine gaps (e.g., founder conviction, what competitors get wrong, who is an *anti-persona*).
- On every substantive update, log what changed and record validated market/user **Learnings** so later sessions do not repeat failed angles.

## Step 2: Strategic Deliverables (Modular — Build Only What Is Asked)

### 1. Origin & Anti-Status Quo (`Why We Exist`)
- **The Enemy (Status Quo)**: What industry habit, bloat, or broken workflow does the founder refuse to accept? Great brands take a clear side.
- **Origin Proof**: Founder insight + real customer pain (in verbatim user language, never generic *"market gap"* filler).

### 2. Vision & Mission (Distinct Roles)
- **Vision (Ambitious, Grounded Future State)**: *"To become [specific role/standard] — built on [concrete pillar 1], [pillar 2], and [pillar 3]."* (2–3 sentences max.)
- **Mission (Daily Execution)**: How the product delivers on the vision today, in observable verbs (not *"empowering teams to unlock synergy"*).

### 3. Behavioral Brand Values (3–5 Rules, Zero Empty Nouns)
Never list buzzwords like *"Innovation, Excellence, Passion, Integrity"*. Define each value as a **visible behavior + tradeoff**:
- **[Value Name]**: What we do in practice (1–2 sentences) — and **what we sacrifice or refuse** to keep it true.

### 4. Category Framing & Positioning (`Obviously Awesome` + Red-Flag Gate)
- **Category Frame**: Compare *Stated Category* vs *Actual Alternatives* customers use today (spreadsheets, manual agencies, generic chatbots) vs *Ownable Space*.
- **2-Axis Territory**: Place alternatives vs this brand on two meaningful buyer axes (e.g., *Generic Prompting ↔ Domain-Grounded Execution*).
- **Positioning Statement**: *"For [specific ICP], [Brand] is the [category] that [differentiator] because [provable reason to believe]."*
- **What We Refuse to Be ("Not For Us")**: 3 explicit boundaries (`"[Brand] is not for people who want..."`).
- **One-Sentence Summary**: ≤ 30 words. Must fail if applied to a competitor (Swap Test).

### 5. Brand Manifesto (Optional — Only When Requested)
Write an emotional, belief-driven declaration distinct from corporate mission copy:
- Choose one deliberate tone: *Quiet Conviction* (editorial certainty), *Provocation* (challenging status quo), *War Cry*, or *Warm Devotion*.
- Structure: Opening conviction (takes a side) → The problem (second-person or declarative) → What we believe instead → The tribe (`"This is for people who..."`) → Non-negotiable commitment → Closing wall-worthy line.
- Provide **Full (300–500 words)** and **Compressed (100–150 words)** versions; ban `"We are..."`, `"we aim to"`, rhymes, and empty buzzwords.

## Guardrails & Sync Rules
- **Evidence First**: Never fabricate market stats, conversion lifts, or unverified proof points; mark hypotheses as hypotheses.
- **Keep `.agents/brand-context.md` Synced**: Save finalized decisions into `.agents/brand-context.md` covering: Brand Basics, Audience & Verbatim Language, Positioning & Anti-Personas, Personality/Tone Sliders, Vision/Mission/Values, Proof Points, First 5 Touchpoints (Homepage, Output/Report, Action Confirmation, First Social Post, Support/Empty State), and Learnings.
