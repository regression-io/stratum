# Discovery Insight: Three Modes of Discovery

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Tentative

---

## The modes

Discovery isn't one activity. It's at least three:

| Mode | What happens | Produces | Direction |
|------|-------------|----------|-----------|
| **Conversational brainstorming** | Two parties riff, challenge, refine | Ideas, framings, questions | Divergent |
| **External knowledge discovery** | Research what exists, what's true, what others have done | Evidence, facts, prior art | Gathering |
| **Prototyping** | Build a throwaway to learn | Hard evidence — what works, what breaks, what surprises | Action |
| **Integration** | Combine insights, iterate, sort confidence, decide | Crystallized artifacts, decisions | Convergent |

These have different rhythms and different roles for the AI:

- **Brainstorming:** AI expands, connects, structures. Human steers, challenges, gates.
- **Research:** AI searches, retrieves, summarizes. Human evaluates relevance and quality.
- **Prototyping:** AI builds, human observes/tests. Or human builds, AI observes/analyzes. The artifact is throwaway; the learning is the output.
- **Integration:** AI proposes synthesis. Human validates, adjusts confidence, decides what holds.

### Each mode produces different confidence

| Mode | Confidence quality |
|------|-------------------|
| Brainstorming | Low — ideas generated, nothing tested |
| Research | Medium — factual evidence, but not yet applied to our context |
| Prototyping | High — we built it and saw what happened. Hardest evidence. |
| Integration | Variable — depends on what inputs it's synthesizing |

## How they interact

Not sequential — they interleave. A brainstorming session surfaces a question → research answers it → the answer reshapes the brainstorm → integration crystallizes what we now know → which opens new questions.

```
brainstorm → question surfaces
                ↓
            research → evidence gathered
                ↓
            integration → confidence sorted, artifact updated
                ↓
            brainstorm → new territory opened by what we learned
                ↓
            ...repeat...
```

The loop is the process. Discovery is done when the loop stops producing new questions — or when the human decides "enough, move on."

## Connection to discovery verbs

The [discovery verbs](discovery-verbs.md) (orient, steer, gather, challenge, etc.) are micro-moves that happen *within* these modes. The modes are the macro-level; the verbs are the micro-level.

**Caveat:** The verbs were intuited from one conversation, not validated. They may be incomplete or wrongly bounded.

## Connection to confidence

Each mode contributes to confidence differently:
- Brainstorming generates options but doesn't validate them (low confidence)
- Research adds evidence (raises confidence on factual claims)
- Integration tests coherence and sorts what holds (raises or lowers confidence based on pressure)

## Open questions

- Are there other modes beyond these four?
- How does Compose represent which mode is active? Does it need to?
- Does the AI switch behavior based on mode, or does the human signal mode changes?
- How does prototyping connect to implementation? A prototype is throwaway, but the learning feeds back into discovery. When does a prototype stop being discovery and start being implementation?
