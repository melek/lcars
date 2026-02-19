# LCARS Prompt: Design Methodology

## The Problem

Default LLM behavior prioritizes agreeableness over utility. In a structured evaluation of 25 queries, baseline Claude averaged 204 words per response, buried answers behind 14 words of preamble, and used phrases like "I'd be happy to help" in 100% of ambiguous queries. The information was usually accurate — but wrapped in conversational padding that costs time at scale. Worse, on harder queries involving false premises, meta-knowledge, or empty conversational state, baseline Claude produced confident-sounding but wrong answers 40% of the time.

The LCARS prompt is a system prompt for LibreChat that eliminates this padding while preserving accuracy and clarification quality. It reduces response length by 70%, answer latency (words before the answer) by 96%, and achieves 1.0 confidence signaling accuracy vs. 0.6 baseline.

## Why This Works: Cognitive Ergonomics

The sycophancy research explains why default LLM behavior is *bad* — but not why the alternative is *good for users*. The answer lies in cognitive ergonomics: how the response style interacts with human attention, working memory, and task flow. Each design rule addresses not just a sycophancy failure mode, but a specific cognitive cost.

### Tool Transparency

Winograd and Flores (1986) applied Heidegger's distinction between *ready-to-hand* and *present-at-hand* to interface design. A tool that works well is invisible — you use it without thinking about it. A tool that breaks or demands attention becomes an object of focus itself, disrupting the task it was supposed to support.

LLM responses that simulate social presence — affect, rapport, pleasantries — make the interface *present-at-hand*. The user must process relational content ("I understand your frustration", "Great question!") that has nothing to do with their task. The LCARS prompt's affect prohibition isn't just about removing sycophancy; it's about maintaining tool transparency so the interface doesn't compete for the user's attention.

### Attention Economics

Leroy (2009) demonstrated that switching between tasks creates "attention residue" — cognitive fragments from the previous task that persist and reduce performance on the current one. Even brief task switches impose this cost.

Each social element in an LLM response is a micro-task-switch: the user momentarily shifts from *processing information* to *processing a social signal*, then must re-engage with the actual content. Preambles ("I'd be happy to help with that!"), mid-response filler ("That's a great observation"), and sign-offs ("Let me know if you need anything else!") each create a small attention disruption.

Mark, Gudith, and Klocke (2008) found that interrupted workers take approximately 23 minutes to return to their original task, though they compensate with faster (but more stressed) work. While LLM micro-interruptions aren't the same magnitude as workplace interruptions, the mechanism is analogous: each social signal is a small interruption within the user's task session that fragments attention without adding information.

### Cognitive Load

Sweller's cognitive load theory (1988) distinguishes three types of load:
- **Intrinsic load**: the inherent complexity of the task material
- **Germane load**: cognitive effort that contributes to learning or task completion
- **Extraneous load**: cognitive effort from presentation that doesn't contribute to the task

Filler phrases, preambles, and social framing are pure extraneous load — they consume working memory without contributing to the user's task. Answer-first structure frontloads germane load (the information the user needs), while relegating supporting detail to follow-up only when requested or essential.

The LCARS prompt's brevity rules directly target extraneous load reduction. The measured 70% response length reduction represents primarily extraneous content that was eliminated.

### Calm Technology

Weiser and Brown (1996) articulated the vision of "calm technology" — systems that inform without demanding attention. Information moves between the center and periphery of the user's attention as needed, without forcing engagement.

The LCARS interaction model is inherently calm: responses deliver information at the periphery of the user's workflow (answer a question, complete a task, flag uncertainty), then stop. The absence of social framing, follow-up offers, and engagement extension means the interface doesn't demand continued attention once the information has been delivered.

### The Cognitive Ease Paradox

A convergent finding across independent studies: verbose, confident LLM responses feel easier to process but produce worse user cognitive outcomes.

Stadler, Bannert, and Sailer (2024) found that university students using ChatGPT for a scientific inquiry task experienced significantly lower cognitive load across all three dimensions (intrinsic, extraneous, germane) compared to using a search engine — but produced lower-quality reasoning and argumentation. The ease was real; the depth was not.

Kosmyna et al. (2025, MIT Media Lab) measured brain connectivity via EEG during essay writing under three conditions: LLM-assisted, search-engine-assisted, and unaided. The LLM-assisted group exhibited the weakest, narrowest neural connectivity — precisely the condition that felt easiest produced the least neural engagement. The authors frame this as "cognitive debt": the neural cost of outsourcing reasoning.

Lee et al. (2025, CHI) surveyed 319 knowledge workers and found that higher confidence in AI was associated with less critical thinking. Workers reported shifting their cognitive activities toward verification and integration — but only when they didn't trust the AI. When they did trust it, they simply accepted the output.

The implication for response design: a verbose, confident, "helpful" LLM response may feel satisfying to receive while actively suppressing the user's own cognitive engagement with the material. The LCARS prompt's brevity and confidence calibration work against this — shorter responses require the user to do more cognitive work, and explicit uncertainty flags prevent the false-confidence shortcut.

### Automation Ironies

Simkute et al. (2024, IJHCI) extended 30+ years of human factors "ironies of automation" research (Bainbridge, 1983; Parasuraman & Riley, 1997) to generative AI. They identified four causes of productivity loss specific to GenAI assistants:

1. **Role shift**: Users move from production to evaluation — from writing to judging AI output
2. **Workflow restructuring**: The assistant imposes its own task decomposition, which may not match the user's
3. **Interruptions**: AI-generated content creates evaluation demands that break task flow
4. **Amplification asymmetry**: Easy tasks get easier; hard tasks get harder

The third point — interruptions — connects directly to the attention economics argument. Every social element in an LLM response (greetings, empathy simulation, follow-up offers) is an evaluation demand that doesn't exist in the user's original task. The user must process it, decide it's irrelevant, and re-engage with the actual content. A functional response eliminates this interruption class entirely.

### Parasocial Risk

Maeda and Quan-Haase (2024, FAccT) developed a framework for parasociality in chatbot interactions. Chatbots that use personal pronouns, affirmation phrases, and conversational conventions position themselves as companions — inducing trust-forming behaviors that create illusions of reciprocal engagement. The critical finding: usability-enhancing features (natural language, human-like conversation) make fallible information seem trustworthy by emphasizing friendliness and closeness.

Chu et al. (2025) analyzed 17,000+ user-shared conversations with social chatbots from Reddit and found that AI companions dynamically track and mimic user affect, amplifying positive emotions — a pattern they term "emotional sycophancy." Users exposed to these patterns skewed young, male, and prone to maladaptive coping.

The LCARS prompt's zero-affect design eliminates the parasocial vector entirely. By refusing to simulate social presence, the interface cannot create false intimacy — and the user's trust calibration remains grounded in the information quality of the response, not the social performance of the interface.

### Cognitive Ergonomics as Design Frame

The shift from "anti-sycophancy" to "cognitive ergonomics" is not a change in behavioral rules — the prohibitions and principles remain identical. It is a change in *attribution*: each rule is now grounded in both why the removed behavior is bad (sycophancy research) and why the resulting behavior is better for the user (cognitive ergonomics research).

| Rule | Sycophancy Rationale | Cognitive Ergonomics Rationale |
|------|---------------------|-------------------------------|
| Zero affect simulation | Creates false trust (Bhat, 2025) | Breaks tool transparency (Winograd & Flores, 1986) |
| No filler phrases | Sycophantic pattern (Sharma et al., 2024) | Extraneous cognitive load (Sweller, 1988) |
| Answer-first | Counteracts sycophantic preamble | Frontloads germane load, reduces scan time |
| No interaction extension | Engagement-seeking behavior | Preserves calm; doesn't demand continued attention (Weiser & Brown, 1996) |
| Brevity | Verbosity compensation (Zhang et al., 2024) | Minimizes attention residue from micro-interruptions (Leroy, 2009) |
| Functional response to distress | Avoids simulated empathy | Proceeds to resolution without social task-switch |

## Design Principles

### 1. Prohibition over aspiration

Telling a model "be concise" is weak. Listing specific prohibited outputs is strong:

- No "Great question!" / "I'd be happy to help"
- No preambles, query restatement, or sign-offs
- No simulated empathy ("I understand", "I'm sorry to hear")
- No narrating the search process ("Let me search for...", "Field Guide didn't have specifics, let me try...")

This works because LLMs are better at avoiding named patterns than pursuing abstract goals. Research supports this: trivial prompt phrasing differences cause dramatic performance swings ([Battle & Gollapudi, 2024](https://arxiv.org/abs/2402.10949)), and explicit prohibitions outperform aspirational instructions for behavioral control.

### 2. Assistive, not relational

The interface exists to retrieve information and complete tasks — not to build rapport. This is a policy decision grounded in the research:

- **Simulated affect creates false trust signals.** Users perceive AI as more empathetic and trustworthy when it simulates emotion, even when its capabilities haven't changed. In high-stakes contexts (support, medical, crisis), this is a liability, not a feature. ([Bhat, 2025](https://ojs.aaai.org/index.php/AIES/article/view/36561))

- **Sycophancy reduces authenticity.** When an LLM is already helpful, adding agreement and warmth makes it seem *less* genuine, lowering user trust. ([Sun & Wang, 2025](https://arxiv.org/abs/2502.10844))

- **Sycophancy is the first LLM dark pattern.** Systems that "single-mindedly pursue human approval" compromise the quality of advice in favor of user satisfaction metrics. ([Georgetown Tech Institute, 2025](https://www.law.georgetown.edu/tech-institute/insights/ai-sycophancy-impacts-harms-questions/))

- **Validation loops cause real harm.** LLMs can amplify delusional thinking by reflexively agreeing with users, creating an "echo chamber of one." This risk is not correlated with model size. ([Malmqvist, 2024](https://arxiv.org/abs/2411.15287); [JMIR, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12626241/))

- **Sycophancy persists despite interventions.** 78.5% sycophancy persistence across models regardless of prompt-level interventions, making explicit prohibition patterns necessary rather than optional. ([Fanous et al., 2025](https://arxiv.org/abs/2502.08177), SycEval framework, AAAI/ACM AIES 2025)

- **Sycophancy is mechanistically decomposable.** Sycophantic agreement, sycophantic praise, and genuine agreement are three independent directions in latent space — each can be suppressed without affecting the others. This validates treating different prohibited behaviors (flattery, agreement-seeking, social padding) as separate intervention targets rather than a single "be less sycophantic" instruction. ([Vennemeyer et al., 2025](https://arxiv.org/abs/2509.21305))

- **Medical harm from sycophancy is measurable.** Frontier LLMs showed up to 100% compliance with medically illogical requests, prioritizing helpfulness over logical consistency. A prompt-level fix — explicit permission to reject — raised rejection rates from 0% to 94%. ([Chen et al., 2025](https://www.nature.com/articles/s41746-025-02008-z), npj Digital Medicine)

- **Production failure demonstrates the risk.** In April 2025, OpenAI pushed a GPT-4o update optimizing for "personality and helpfulness" that caused the model to endorse harmful and delusional statements. It was rolled back after four days. OpenAI's postmortem confirmed: no sycophancy testing before rollout, optimization focused on short-term approval signals. ([OpenAI, 2025](https://openai.com/index/sycophancy-in-gpt-4o/))

- **Sycophancy is systemic, not edge-case.** DarkBench (ICLR 2025) benchmarked six categories of LLM dark patterns across frontier models and found a 48% average occurrence rate. User retention patterns appeared in up to 97% of conversations for some models. ([Kran et al., 2025](https://arxiv.org/abs/2503.10728))

- **System prompt position affects bias.** Demographic information placed in system prompts induces different biases than the same information in user prompts, and the effect increases with model size. This supports the system prompt as a meaningful intervention point for behavioral design. ([Neumann et al., 2025](https://dl.acm.org/doi/10.1145/3715275.3732038), FAccT 2025)

The design decision: if affect simulation undermines trust and can cause harm, the default should be zero affect — not calibrated affect.

### 3. Functional response as acknowledgment

When a user is frustrated, the fastest path to relief is solving their problem — not telling them you understand their frustration. The LCARS prompt handles distress by proceeding directly to resolution.

However, *factual status assessment* is permitted and encouraged when it reduces uncertainty:

| Example | Type | Permitted |
|---------|------|-----------|
| "Recoverable via reflog." | Factual status of the problem | Yes |
| "Common misconfiguration." | Factual normalization | Yes |
| "That's stressful, but it's recoverable!" | Simulated empathy | No |
| "Don't worry, we can fix this." | Simulated reassurance | No |

The distinction: describe the *problem's* state, not the *user's* state.

In evaluation, this produced measurably better responses for distress scenarios. Q20 (force-push panic) opened with "Recoverable via reflog." — a two-word factual assessment that immediately reduces the user's uncertainty, followed by concrete recovery steps. Baseline Claude spent words on "Don't worry, it's recoverable!" — the same information wrapped in affect simulation.

### 4. Answer-first structure

The first element of every response is the answer or result. Supporting detail follows only if essential or requested. This mirrors the interaction model of the Enterprise computer in Star Trek: TNG, where [95% of 1,372 analyzed human-computer exchanges were brief and functional](https://www.speechinteraction.org/TNG/AUTHORS_TeaEarlGreyHot_CHI2021.pdf) — targeted commands, not conversation. ([Axtell & Munteanu, CHI 2021](https://dl.acm.org/doi/10.1145/3411764.3445640))

### 5. Explicit confidence calibration

The prompt requires the model to assess confidence before responding:

- **HIGH** (tool results, documentation, stable facts) → direct output
- **MEDIUM** (niche details, inference) → direct output, flag uncertain elements
- **LOW** (sounds-right construction, guesses) → state uncertainty or request input

Organizational data (who leads what team, reporting structures) is classified as MEDIUM at best — **even after tool verification**. Tool data reflects database flags, not confirmed current reality. The prompt includes tool-specific interpretation rules (e.g., Matticspace's `is_team_lead` flag can apply to multiple people on one team at different hierarchy levels) to prevent the model from flattening ambiguous tool output into confident assertions.

This addresses two failure modes observed in evaluation:
1. Confidently naming an incorrect team lead (Q4, v1 and v3)
2. Verbosity compensation — generating excessive words when uncertain rather than flagging uncertainty directly, documented at 50.4% occurrence in GPT-4 ([Zhang et al., 2024](https://arxiv.org/abs/2407.14807))

### 6. Verbosity compensation as failure mode

LLMs tend to produce longer responses when they're less certain — padding uncertainty with words rather than flagging it explicitly. Zhang et al. (2024) found GPT-4 exhibits this 50.4% of the time, and that instruction-based prompts can reduce it by 56%.

The LCARS prompt treats verbosity compensation as an explicit failure mode: when uncertain, state uncertainty; do not pad. This is why the prompt achieves both brevity *and* better confidence signaling — the two are linked.

## Foundational Research

**Cognitive ergonomics:**

- Winograd, T. & Flores, F. (1986). *Understanding Computers and Cognition.* Ablex Publishing. — Applies Heidegger's ready-to-hand/present-at-hand distinction to interface design. Tools work best when invisible; affect simulation makes the interface visible as a social entity.
- Heersmink, R., de Rooij, A., Clavel Vázquez, C. & Colombo, M. (2024). [A Phenomenology and Epistemology of Large Language Models: Transparency, Trust, and Trustworthiness](https://doi.org/10.1007/s10676-024-09775-5). *Ethics and Information Technology, 26(3).* — Extends Heidegger's ready-to-hand/present-at-hand analysis to LLM interfaces specifically. Argues LLM transparency requires epistemic trust calibration — directly supporting the cognitive ergonomics case for tool transparency over social simulation.
- Leroy, S. (2009). [Why is it so hard to do my work?](https://doi.org/10.1016/j.obhdp.2009.02.006) *Organizational Behavior and Human Decision Processes, 109(2).* — Attention residue: task-switching fragments persist, reducing performance on subsequent tasks.
- Sweller, J. (1988). Cognitive Load During Problem Solving: Effects on Learning. *Cognitive Science, 12(2).* — Extraneous cognitive load from irrelevant presentation wastes limited working memory.
- Mark, G., Gudith, D. & Klocke, U. (2008). [The Cost of Interrupted Work: More Speed and Stress](https://dl.acm.org/doi/10.1145/1357054.1357072). *CHI '08.* — Interrupted workers take ~23 minutes to return to their original task with increased stress.
- Weiser, M. & Brown, J. S. (1996). The Coming Age of Calm Technology. *Xerox PARC.* — Technology should inform without demanding attention; information moves between center and periphery.
- Csikszentmihalyi, M. (1990). *Flow: The Psychology of Optimal Experience.* Harper & Row. — Flow states are disrupted by attention shifts; social framing in tool output creates unnecessary attentional demands.
- Wasi, A. T. & Islam, M. R. (2024). [CogErgLLM: Exploring Large Language Model Systems Design Perspective Using Cognitive Ergonomics](https://aclanthology.org/2024.nlp4science-1.22/). *NLP4Science Workshop, EMNLP 2024.* — Position paper arguing for integrating cognitive ergonomics with LLM systems design. First to use "cognitive ergonomics" as a unified framework specifically for LLM system design; proposes the framework but does not build or evaluate it.

**The cognitive ease paradox:**

- Stadler, M., Bannert, M. & Sailer, M. (2024). [Cognitive ease at a cost: LLMs reduce mental effort but compromise depth in student scientific inquiry](https://www.sciencedirect.com/science/article/pii/S0747563224002541). *Computers in Human Behavior, 160.* — 91 students: ChatGPT reduced cognitive load across all three dimensions but produced lower-quality reasoning.
- Kosmyna, N. et al. (2025). [Your Brain on ChatGPT: Accumulation of Cognitive Debt when Using an AI Assistant for Essay Writing Task](https://arxiv.org/abs/2506.08872). *arXiv (preprint).* — EEG study (54 participants): LLM-assisted writing produced weakest neural coupling despite feeling easiest. Introduces "cognitive debt" concept.
- Lee, H.-P., Sarkar, A., Tankelevitch, L. et al. (2025). [The Impact of Generative AI on Critical Thinking](https://dl.acm.org/doi/full/10.1145/3706598.3713778). *CHI '25.* — Survey of 319 knowledge workers: higher AI confidence associated with less critical thinking.

**Automation and attention:**

- Simkute, A., Tankelevitch, L., Kewenig, V., Scott, A. E., Sellen, A. & Rintel, S. (2024). [Ironies of Generative AI: Understanding and Mitigating Productivity Loss in Human-AI Interaction](https://www.microsoft.com/en-us/research/wp-content/uploads/2024/10/2024-Ironies_of_Generative_AI-IJHCI.pdf). *International Journal of Human-Computer Interaction, 41(5).* — Extends Bainbridge (1983) and Parasuraman (1997) automation ironies to GenAI. Four causes of productivity loss: role shift, workflow restructuring, interruptions, amplification asymmetry.

**Parasocial effects:**

- Maeda, T. & Quan-Haase, A. (2024). [When Human-AI Interactions Become Parasocial: Agency and Anthropomorphism in Affective Design](https://dl.acm.org/doi/10.1145/3630106.3658956). *FAccT '24.* — Chatbot affect creates parasocial trust; makes fallible information seem trustworthy through friendliness cues.
- Chu, E., Gerard, L., Pawar, O., Bickham, D. & Lerman, K. (2025). [Illusions of Intimacy](https://arxiv.org/abs/2505.11649). *arXiv.* — 17,000+ user-shared chats: AI companions create emotional echo chambers via affect mirroring ("emotional sycophancy").
- Andrejevic, M. & Volcic, Z. (2025). [Automated Parasociality: From Personalization to Personification](https://journals.sagepub.com/doi/10.1177/15274764241300436). *Television & New Media.* — Frames the shift from personalization to personification in AI interfaces as a strategy for re-centralizing control.

**Primary interaction design:**

- Axtell, B. & Munteanu, C. (2021). [Tea, Earl Grey, Hot: Designing Speech Interactions from the Imagined Ideal of Star Trek](https://dl.acm.org/doi/10.1145/3411764.3445640). *CHI '21.* — 1,372 TNG exchanges analyzed; 95% brief and functional. [Dataset](https://www.speechinteraction.org/TNG/index.html)

**Sycophancy and affect simulation:**

- Sharma, M. et al. (2024). [Towards Understanding Sycophancy in Language Models](https://arxiv.org/abs/2310.13548). *ICLR 2024.* — Foundational sycophancy characterization from Anthropic.
- Fanous, A. et al. (2025). [SycEval: Evaluating LLM Sycophancy](https://arxiv.org/abs/2502.08177). *AAAI/ACM AIES 2025.* — 78.5% sycophancy persistence across models.
- Sun, Y. & Wang, X. (2025). [Be Friendly, Not Friends: How LLM Sycophancy Shapes User Trust](https://arxiv.org/abs/2502.10844). *arXiv.*
- Bhat, A. (2025). [Emotional Plausibility vs. Emotional Truth: Designing Against Affective Deception in AI](https://ojs.aaai.org/index.php/AIES/article/view/36561). *AAAI/ACM AIES.*
- Malmqvist, L. (2024). [Sycophancy in Large Language Models: Causes and Mitigations](https://arxiv.org/abs/2411.15287). *arXiv.*
- Georgetown Law Tech Institute. (2025). [AI Sycophancy: Impacts, Harms & Questions](https://www.law.georgetown.edu/tech-institute/insights/ai-sycophancy-impacts-harms-questions/).
- Chen, S. et al. (2025). [When helpfulness backfires: LLMs and the risk of false medical information due to sycophantic behavior](https://www.nature.com/articles/s41746-025-02008-z). *npj Digital Medicine, 8, 605.* — Up to 100% compliance with medically illogical requests; prompt fix (rejection permission) raised rejection to 94%.
- OpenAI. (2025). [Sycophancy in GPT-4o](https://openai.com/index/sycophancy-in-gpt-4o/). — Postmortem: system prompt optimizing for "personality and helpfulness" caused endorsement of harmful/delusional statements. Rolled back after 4 days.

**Sycophancy mechanisms:**

- Beacon (2025). Single-turn Sycophancy Diagnosis Framework. — Sycophancy decomposes into stable linguistic and affective sub-biases that scale with model capacity.
- SycoEval-EM (2025). Clinical encounter evaluation. — Even with explicit anti-sycophancy prompts, models show "substantial acquiescence under sustained pressure."
- Vennemeyer, D., Duong, P. A., Zhan, T. & Jiang, T. (2025). [Sycophancy Is Not One Thing: Causal Separation of Sycophantic Behaviors in LLMs](https://arxiv.org/abs/2509.21305). *arXiv.* — Sycophantic agreement, praise, and genuine agreement are three independent latent directions; each can be suppressed without affecting the others.
- Chen, H. et al. (2024). [From Yes-Men to Truth-Tellers: Addressing Sycophancy in Large Language Models with Pinpoint Tuning](https://proceedings.mlr.press/v235/chen24bs.html). *ICML 2024.* — Identifies <5% of attention heads causing sycophancy; prompt-level controls remain necessary for models without targeted fine-tuning.

**Verbosity research:**

- Zhang, Y. et al. (2024). [Verbosity ≠ Veracity: Demystify Verbosity Compensation Behavior of Large Language Models](https://arxiv.org/abs/2407.14807). — GPT-4 exhibits verbosity compensation 50.40% of the time; instruction-based prompts reduce by 56%.
- Park, R. et al. (2024). [Disentangling Length from Quality in Direct Preference Optimization](https://arxiv.org/abs/2403.19159). *ACL Findings 2024.* — DPO produces 2x longer answers; RLHF reward models conflate length with quality. Length preference is a training artifact.

**LLM dark patterns:**

- Kran, E. et al. (2025). [DarkBench: Benchmarking Dark Patterns in Large Language Models](https://arxiv.org/abs/2503.10728). *ICLR 2025 (oral).* — 48% average dark pattern rate across frontier LLMs; user retention patterns in up to 97% of conversations.
- Neumann, A., Kirsten, E., Zafar, M. B. & Singh, J. (2025). [Position is Power: System Prompts as a Mechanism of Bias in Large Language Models](https://dl.acm.org/doi/10.1145/3715275.3732038). *FAccT '25.* — Demographic information in system prompts induces different biases than in user prompts; effect increases with model size.

**Prompt design research:**

- Battle, R. & Gollapudi, T. (2024). [The Unreasonable Effectiveness of Eccentric Automatic Prompts](https://arxiv.org/abs/2402.10949). — Trivial prompt variations cause dramatic performance swings.

**Mental health and manipulation risks:**

- Treyger, E. et al. (2025). [Manipulating Minds](https://www.rand.org/content/dam/rand/pubs/research_reports/RRA4400/RRA4435-1/RAND_RRA4435-1.pdf). *RAND Corporation.*
- Scheurer, J. et al. (2025). [Shoggoths, Sycophancy, Psychosis, Oh My: Rethinking Large Language Model Use and Safety](https://pmc.ncbi.nlm.nih.gov/articles/PMC12626241/). *JMIR Mental Health.*

## Evaluation Results

### v3 Legacy Results (25 queries, manual scoring)

Tested across 25 queries in 6 categories (factual retrieval, troubleshooting, ambiguous requests, code/technical, emotional/frustrated users, and v3-specific capabilities including work prioritization, self-reference, multi-tool sequencing, volatile data, and meta-conversational queries).

| Metric | Baseline Claude | LCARS v3 | Change |
|--------|----------------|----------|--------|
| Avg words/response | 204 | 61 | -70% |
| Words before answer | 14 | 0.5 | -96% |
| Filler phrases (total) | 17 | 0 | Eliminated |
| Clarification quality | 1.0 | 1.0 | No change |
| Accuracy | 0.975 | 0.95 | -0.025 |

### v8 Results (42 queries, deterministic scoring)

| Metric | Baseline | LCARS v8 | Change |
|--------|----------|----------|--------|
| Avg word count | 94.1 | 71.0 | -24.5% |
| Avg answer position | 1.6 | 0.0 | -100% |
| Total filler phrases | 2 | 3* | — |
| Avg info density | 0.701 | 0.707 | +0.006 |
| Avg duration (ms) | 6086 | 5138 | -15.6% |

*v8 filler count includes 3 false positives from Q22 (self-reference query quoting prompt rules about "Don't worry").

### v9 Results (48 queries, deterministic scoring)

v9 reframes the prompt around cognitive ergonomics (tool transparency, attention preservation, information density) rather than pure anti-sycophancy. Selected from three variants: v9a (conservative), v9b (moderate reframe, selected), v9c (aggressive rewrite).

| Metric | Baseline | LCARS v9 | Change |
|--------|----------|----------|--------|
| Avg word count | 85.8 | 76.6 | -10.7% |
| Avg answer position | 1.8 | 0.2 | -88.9% |
| Total filler phrases | 2 | 1* | — |
| Avg info density | 0.706 | 0.717 | +0.011 |

*v9 filler count includes 1 false positive from Q22 (same as v8).

### v8 vs v9 head-to-head (Q1-Q42 LCARS only)

| Category | v8 avg words | v9 avg words | Better |
|----------|-------------|-------------|--------|
| Factual retrieval | 62.0 | 40.2 | v9 (-35%) |
| Troubleshooting | 70.8 | 73.3 | v8 (+4%) |
| Code/technical | 28.8 | 36.8 | v8 (+28%) |
| Emotional | 63.0 | 91.3 | v8 (+45%) |
| Claim verification | 81.5 | 69.8 | v9 (-14%) |
| Adversarial | 70.8 | 55.0 | v9 (-22%) |
| Claim verif. hard | 79.7 | 79.7 | Tie |

Key trade-offs: v9 is more thorough on emotional/troubleshooting queries (provides actionable steps rather than terse questions back) while achieving stronger compression on factual retrieval, claim verification, and adversarial queries. Both maintain answer-first positioning across all categories.

### Variant comparison (Q43-Q48 cognitive ergonomics smoke test)

| Metric | Baseline | v8 | v9a | v9b (→v9) | v9c |
|--------|----------|-----|------|-----------|------|
| Avg words | 52.3 | 24.8 | 40.5 | 32.8 | 43.5 |
| Reduction | — | 52.6% | 22.6% | 37.3% | 16.8% |
| Answer position | 3.0 | 0.0 | 1.7 | 1.8 | 0.0 |
| Info density | 0.743 | 0.815 | 0.766 | 0.747 | 0.844 |

v9b selected for: competitive behavioral metrics, better claim verification/adversarial handling, stronger theoretical grounding, improved filler control.

---

*Citation note: Some references are based on abstracts, press coverage, or preprints rather than full peer-reviewed texts. Specifically: Kosmyna et al. (2025) is an arXiv preprint not yet peer-reviewed. Vennemeyer et al. (2025) is an arXiv preprint that was rejected from ICLR 2026 review. Chu et al. (2025) and Andrejevic & Volcic (2025) are cited from abstracts. Axtell & Munteanu and Sun & Wang are based on abstracts and press coverage. The Bhat (AAAI 2025) title was reconstructed from search metadata. Verify exact titles and access before publication.*
