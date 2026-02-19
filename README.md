# RAG-LLM-Augmented BIM for Automated Fall Hazard Identification and Prevention

## Abstract

Current Automated Rule-Checking (ARC) methods assess BIM models against safety requirements but use hard-coded rules and manual processes that are time-consuming and error-prone. Recent Large-Language Models (LLMs) with Retrieval-Augmented Generation (RAG) enable automated interpretation of regulations; however, prior studies mainly address code compliance, provide limited treatment of fall hazards, struggle with geometric reasoning, and focus on guidance over prevention. This paper proposes RAG-LLM-augmented BIM for automated fall hazard identification and prevention. Fall regulations were structured using ontology to establish geometric, semantic, and spatial relationships with BIM elements. Detected hazards were visualized using severity- and hazard-based color coding, and OSHA-compliant guardrails were installed with rationale-based advisories. Detection engine achieved 97.7% geometric success in hazard detection, with 100% visualization and guardrail placement accuracy. The pipeline showed 2.4s response time, 100% retrieval performance, and 0.985 precision. This study advances Design-for-Safety (DfS) techniques and positions RAG-LLM-augmented BIM as an enabler of construction safety management.

## Keywords
Retrieval augmented generation, Large language models, Building information modeling, Automated rule checking, Design for Safety, Fall hazards.

## Project phases and details
### Phase 1: Fall Hazard Identification
a) Developed an ontology-driven hazard detection engine that integrates fall safety regulations with IFC4x3 BIM models.
b) Enabled automated geometric and semantic reasoning to identify fall hazards such as unprotected edges, floor openings, and stair risks.
c) Achieved high detection accuracy (97.7%) with real-time processing (~1 second).
d) Introduced structured hazard output (JSON format) including severity, thresholds, and spatial context for downstream tasks.
e) Eliminated reliance on manual rule encoding by formalizing regulation-to-geometry mapping via ontology.

### Phase 2: Hazard Visualization
a) Implemented IFC-based hazard visualization with direct embedding into BIM models.
b) Designed a dual visualization strategy: 1) Surface coloring for solid elements (walls, slabs, stairs) and 2) Proxy markers for void-based hazards (openings)
c) Introduced severity-based and hazard-type color coding for intuitive risk interpretation.
d) Achieved 100% visualization coverage of detected hazards.
e) Enabled improved spatial awareness and safety communication during design review.

### Phase 3: Fall Prevention / Guardrails
a) Developed a fully automated guardrail generation system using geometric reasoning.
b) Implemented OSHA-compliant safety measures (top rail, mid rail, toe board) directly in BIM.
c) Enabled context-aware placement: 1) Edge detection on slabs, 2) Opening protection, and 3) Stairway safety handling
d) Introduced wall-aware and geometry-driven boundary analysis for precise placement.
e) Achieved 100% accuracy in guardrail generation, minimizing manual intervention.

### Phase 4: RAG-LLM Safety Advisor
a) Built a RAG-enhanced LLM pipeline for intelligent safety reasoning and advisory.
b) Integrated BIM hazard data + regulatory documents + best practices into a unified knowledge base.
c) Enabled context-aware, explainable safety recommendations grounded in regulations.
d) Achieved high performance (Precision: 0.985, 100% retrieval accuracy, ~2.4s response time).
e) Reduced hallucination by ensuring LLM responses are grounded in retrieved safety knowledge.
f) Supported multi-turn conversational safety analysis for design decision-making.

### Phase 5: Integrated GUI System
a) Developed a production-grade GUI (Tkinter-based) integrating all four phases into a single pipeline.
b) Enabled end-to-end automation: IFC input → Detection → Visualization → Prevention → Advisory
c) Implemented multithreaded architecture for responsive and real-time processing.
d) Designed session-based data management for traceability and reproducibility.
e) Generated a unified Master RAG dataset combining outputs from all phases.
f) Provided an interactive interface for users to query safety insights with full BIM context.
