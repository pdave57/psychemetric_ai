# PsychemetreAI / Agent Bleu RAG Corpus Implementation Plan

## 1. Executive Summary & Corpus Blueprint
This plan translates the **Corpus Content Specification**, **Candidate Sources Catalog**, and **Chunking Rules** into an automated, license-gated RAG pipeline in `app/knowledge/`.

### Five Core Knowledge Areas & PDF Mapping
| Knowledge Area | Description | Primary Sources & PDF Files | Target Extraction Focus | License |
|---|---|---|---|---|
| **Temperament concepts** | What temperament is; mood vs personality; biological/affective foundations; classical temperaments & TEMPS subscales (depressive, cyclothymic, hyperthymic, irritable, anxious) | - `TEMPS-A.pdf`<br>- `The complex genetics and biology of human.pdf`<br>- `four-temperaments-guidebook.pdf`<br>- `The Balance of Personality.pdf` | Distinct definitions of temperament vs transient mood states; the 4 classical types & 5 TEMPS affective dimensions | CC BY 4.0 / CC BY-NC-SA 4.0 |
| **Personality and trait models** | Trait theory, Big Five, stability over time, person-situation debate, how temperaments map to traits | - `The Balance of Personality.pdf` (Ch. 1 Traits, Ch. 2 Stability)<br>- `OpenStax.pdf` (Ch. 11 Personality) | Lexical hypothesis, Five-Factor Model, temporal stability, interactionist perspective | CC BY-NC-SA 4.0 / CC BY 4.0 |
| **Emotion** | Basic emotions, appraisal theory, dimensional models (valence/arousal), feeling now vs emotional tendency | - `OpenStax.pdf` (Ch. 10 Emotion & Motivation)<br>- `noba.pdf` (Emotion chapters) | James-Lange, Cannon-Bard, Schachter-Singer, cognitive appraisal, circumplex model | CC BY 4.0 / CC BY-NC-SA 4.0 |
| **Assessment literacy** | Reliability, validity, limits of self-report, why a score is not a diagnosis, norming & standard error | - `The Balance of Personality.pdf` (Ch. 3 Assessment)<br>- `OpenStax.pdf` (Ch. 11.10 Assessment)<br>- `standards_2014edition.pdf` (Synthesized reference only, no raw text redistribution) | Test-retest, internal consistency (Cronbach's alpha), construct validity, non-diagnostic reflective framing | CC BY-NC-SA 4.0 / Internal synthesized guidance |
| **Wellbeing and safety** | Grounding, unhooking, emotional regulation, boundary setting, crisis resources, what the agent should and should not claim | - `Doing-What-Matters.pdf` (WHO stress management guide)<br>- `OpenStax.pdf` (Ch. 14 Stress Regulation)<br>- Clinician safety protocols | 5-4-3-2-1 grounding, unhooking from difficult thoughts, professional support triggers | CC BY-NC-SA 3.0 IGO / CC BY 4.0 |

---

## 2. Ingestion & Chunking Architecture
```
knowledge_base/ (Raw PDFs)
       │
       ▼
app/knowledge/corpus_loader.py ───▶ [PDF Text Extractor & Chapter Segmenter]
       │
       ▼
app/knowledge/chunking.py ────────▶ [Semantic Concept Chunker]
       │                            - Filters out case studies & disorder/diagnostic text
       │                            - Attaches metadata: source, license, topic, subscale, concept
       ▼
app/knowledge/ingestion.py ───────▶ [License & Integrity Gate]
       │                            - Verifies license string
       │                            - Idempotent by SHA-256
       ▼
PostgreSQL / SQLite Database ─────▶ `knowledge_documents` & `knowledge_chunks`
       │                            (with 1536-dim vector embeddings)
       ▼
app/knowledge/retrieval.py ───────▶ [Hybrid Search (Semantic + BM25/Keyword + Evidence Boost)]
```

---

## 3. Strict Chunking Rules & Quality Control
1. **Concept-Based Sizing**: Chunks are 150–350 words centered on a single conceptual unit (e.g., *"Hyperthymic temperament definition"*, *"Construct validity vs face validity"*, *"Autonomic stress response"*), rather than arbitrary page splits.
2. **Deterministic Exclusions**:
   - Exclude DSM-5 / ICD diagnostic criteria, therapy intervention protocols, or psychiatric pathology chapters (which would invite diagnostic language).
   - Exclude bibliography lists, index tables, and publisher copyright front-matter.
3. **Structured Metadata Schema**:
   - `topic`: `temperament` | `personality_science` | `emotional_intelligence` | `assessment_literacy` | `wellbeing_and_safety`
   - `subscale`: `sanguine` | `choleric` | `melancholic` | `phlegmatic` | `depressive` | `cyclothymic` | `hyperthymic` | `irritable` | `anxious` | `general`
   - `concept`: Short descriptive tag (e.g., `grounding_54321`, `temperament_vs_personality`, `reliability_definition`)
   - `license`: Full license string (e.g., `CC BY-NC-SA 4.0`, `CC BY 4.0`)
   - `evidence`: `expert_reviewed` | `research_supported` | `clinical_guideline`
