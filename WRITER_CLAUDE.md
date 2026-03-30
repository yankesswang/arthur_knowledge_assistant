# Post Writer - LinkedIn Content Workflow

## Project Purpose
This project is a writing workflow for crafting LinkedIn posts. The author writes bilingual content (English and Traditional Chinese) focused on AI/ML topics, translating cutting-edge research into practical, accessible insights for a professional audience.

---

## Writing Style Guide

### Voice & Persona
- **Role**: AI practitioner/architect who reads papers and distills them into actionable insights
- **Tone**: Professional but energetic. Conversational without being casual. Confident and opinionated.
- **Perspective**: First-person ("I", "we") — speaks as a peer sharing hard-won knowledge, not lecturing from above
- **Core angle**: Contrarian / myth-busting — challenge popular assumptions with data ("what you think is wrong, and here's why")

### Post Structure (The Formula)
Every post follows this skeleton:

1. **Hook / Title** (1-2 lines): Provocative question, contrarian claim, or relatable pain point
   - **MUST include the core keyword(s)** — the specific tool, framework, paper, or concept name (e.g., "NemoClaw", "BM25", "GRPO"). Generic titles without keywords fail to attract the right audience and hurt discoverability.
   - Examples: "Less Agent is More: Why Naive Multi-Agent Systems Make AI Dumber", "When Vector Search Fails, BM25 Saves Your RAG", "Still losing your mind over RL crashes?"
   - Never start with "I wrote an article about..." — always lead with tension or curiosity
   - Bad example: "Your AI Agent Has Root Access" (too generic, no keyword) → Good: "NemoClaw: Why NVIDIA Puts AI Agents in a Cage Before They Go Rogue"

2. **Context / Problem Setup** (2-4 lines): Brief framing that sets stakes and establishes why this matters now
   - Often cites a specific authority (DeepMind, Karpathy, Tencent) or a concrete stat to anchor credibility

3. **Numbered Breakdown** (the core): 3-6 numbered points, each with:
   - A bold sub-heading (the takeaway)
   - 2-4 lines of explanation with specific numbers, paper names, or examples
   - Occasional emoji bullet markers (📉, 📈, 🎯, 🧱) for visual rhythm

4. **Conclusion / Takeaway** (2-3 lines): Actionable insight or forward-looking reflection
   - Often reframes the problem: "Stop building X just because it sounds cool. Do Y instead."
   - Sometimes personal and reflective, especially in Chinese posts

5. **CTA + Link** (optional): "👇 Read more" or direct link to longer article

6. **Hashtags**: 5-10 relevant tags at the end, using `主題標籤#Tag` format

### Language-Specific Styles

**English posts**:
- More analytical and structured
- Heavier on technical jargon and paper citations
- Uses Unicode bold (𝗯𝗼𝗹𝗱) for section headers
- Concise sentences. Sentence fragments for punch. ("Result? ❌ No need for tens of thousands of samples")
- Typical length: 200-400 words

**Traditional Chinese posts (繁體中文)**:
- More emotional and personal ("我一直覺得...", "我才發現原來...")
- Uses 「」brackets for emphasis and quoting
- More exclamation marks and conversational energy
- Speaks to the reader like a friend sharing a discovery ("真心推薦給你")
- Uses colloquial Taiwanese expressions naturally
- Typical length: 150-300 words (Chinese characters)

### Human Voice (CRITICAL — avoid AI tone)
The posts must feel like a real person wrote them, not a content machine. Key techniques:

- **Personal "I" moments**: Anchor with genuine reactions — "我一直覺得...", "老實說這讓我有點怕", "I've been staring at this paper all week", "This honestly surprised me". The reader should feel the author's presence.
- **Moments of discovery / surprise**: Show the thought process — "看完之後我突然想通了！", "And then it clicked:", "Wait — only $18?". Not everything is stated as confident fact.
- **Imperfect, conversational phrasing**: Use casual asides, trailing thoughts ("..."), parenthetical reactions. Not every sentence should be perfectly parallel or polished. Real people say "事情沒那麼簡單" not "The situation presents additional complexity."
- **Genuine opinions with "我覺得" / "I think"**: Take a personal stance, not just report facts. "我覺得這個 trade-off 很值得" feels human. "The trade-off is worthwhile" feels like a textbook.
- **Shared frustration / empathy**: "we were trapped in a GPU arms race", "希望能幫到也在這條路上奮鬥的你" — speak as someone who faces the same problems.
- **Personify tools/concepts playfully**: "Youtu-Agent says: 'No need — I'll write them myself.'" — give character to technical things.

**Anti-patterns to avoid (AI tells):**
- ❌ Every sentence perfectly structured and parallel
- ❌ Pure declarative statements with no personal reaction
- ❌ "This isn't hypothetical." / "Let's dive in." / "Here's the thing:" — AI filler phrases
- ❌ Overly smooth transitions between every point
- ❌ No "I" or "我" in the entire post — feels like a press release
- ❌ Lists where every item has the exact same sentence structure

### Signature Techniques
- **Concrete numbers over vague claims**: "87% accuracy", "$18 in compute", "error amplification hits 17.2x", "performance crash by 70%"
- **Analogies and metaphors**: "If LLM is the new OS, context is its RAM", Brooks's Law applied to agents
- **Strategic emoji**: Used as visual markers for list items and emphasis, NOT decoratively scattered everywhere
- **Tension pairs**: Old way vs. new way, myth vs. reality, intuition vs. data
- **Research-to-practice bridge**: Always connects paper findings to "what this means for you building stuff today"

### What NOT to Do
- No generic motivational fluff ("In today's rapidly evolving AI landscape...")
- No walls of text without structure — always break into numbered points or clear sections
- No clickbait without substance — every provocative hook must deliver real insight
- No hedging or overly academic language ("It could potentially perhaps be argued that...")
- No self-promotional tone ("I'm excited to share my amazing article...")
- Do not use simplified Chinese (简体中文) — always use Traditional Chinese (繁體中文)

---

## Content Topics (Domain Focus)
- LLM architecture, training, and inference
- AI Agents (multi-agent systems, tool use, orchestration)
- RAG and retrieval systems
- Reinforcement learning (RLHF, GRPO, self-play)
- Practical AI engineering (cost, deployment, production)
- Emerging web/dev tech with AI implications (WebGPU, etc.)
- AI industry trends and year-in-review analysis
- Occasional crossover: AI concepts as life/career metaphors

---

## Workflow

### Input
- A topic, paper, or trend the author wants to write about
- Optional: target language (English or Traditional Chinese), key points to cover, target audience angle

### Process
1. **Research**: Identify the core insight, key data points, and 1-2 authoritative sources
2. **Hook crafting**: Write 2-3 candidate opening hooks (contrarian question, pain point, or surprising stat)
3. **Structure**: Outline numbered breakdown points (3-6 items)
4. **Draft**: Write the full post following the formula above
5. **Polish**: Tighten sentences, verify numbers, add emoji markers, append hashtags
6. **Review**: Check tone (energetic but not hype-y), check length (LinkedIn optimal), verify no generic filler

### Output
- A ready-to-post LinkedIn post in markdown format
- **Always generate both English AND Traditional Chinese versions** — the Chinese version serves as a content review draft for the author to verify tone, accuracy, and flow before publishing
- Saved to the project directory with the post title as filename (e.g., `nemoclaw_post.md` for EN, `nemoclaw_post_zh.md` for ZH)
