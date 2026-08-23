# LLM Router

**Stage:** S6 — Effect
**Realizes:** 02.3.8 and the ten-stage prompt pipeline of 02.8.5, per 21B §20
**Depends on:** Layer 0, Trust, Memory, Cost Manager
**CIR-001 status:** **not blocked** — an internal abstraction over model
tiering, not a governed external relationship (21B §20.4)

## The ten-stage pipeline (02.8.5)

21B §20.4: **"The prompt pipeline is fixed in order."**

1. Template selection · 2. Context retrieval · 3. Context assembly ·
4. Input sanitization · 5. Prompt rendering · 6. Token budget check ·
7. Invocation · 8. Output parsing · 9. Grounding validation · 10. Cache storage

Three orderings carry constitutional weight, and each has its own test:

- **Sanitization precedes rendering** — untrusted context must not reach a
  rendered prompt unsanitized.
- **The budget check precedes invocation** — a request that cannot afford to
  run must not run.
- **Grounding validation precedes cache storage** — an ungrounded answer must
  never be cached, or one hallucination becomes a permanent one served free.

`PipelineTrace` refuses a stage that does not advance, so a reordering is an
exception rather than a silent constitutional breach.

## Tiering and failover

Nano and Standard are local; Premium is external. The failover chain degrades
downward, so **Premium becoming unavailable falls back rather than failing** —
which is what makes `01.3.1` Local First structural rather than aspirational.

## Open items

- **No real model backend.** `ModelBackend` is a Protocol; Ollama, vLLM and
  LiteLLM from the canonical stack are not wired in.
- **Token estimation is four-characters-per-token**, not a real tokenizer. It
  errs high, so the budget check is conservative rather than permissive.
- **Grounding validation is vocabulary overlap**, deliberately simple. It will
  not catch a subtle fabrication. What it does enforce reliably is that an
  ungrounded answer never reaches the cache.
- The semantic cache is exact-match only; semantic similarity needs the
  embedding stack.
- Performance is unvalidated.
