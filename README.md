# RAG-LLM-Augmented BIM for Automated Fall Hazard Identification and Prevention during Design

## Abstract

Current automated rule-checking methods for construction safety rely on hard-coded rules, manual interpretation, and fragmented workflow, limiting their adaptability for proactive fall-hazard prevention. Although Retrieval-Augmented Generation (RAG)-enhanced Large Language Models (LLMs), Building Information Modeling (BIM)-based rule checking, and ontology-based reasoning are well established, their integration into a unified fall-specific workflow remains limited. This paper develops RAG-LLM-augmented BIM method for automated fall-hazard identification and prevention. The framework integrates regulatory knowledge, an ontology-guided fall-safety model, Industry Foundation Classes (IFC)-based geometric reasoning, hazard visualization, guardrail generation, and RAG-LLM advisory through shared structured records. These records integrate IFC geometry, semantic BIM classes, regulatory thresholds, severity logic, prevention status, and retrieved safety knowledge, providing a common evidence layer across the pipeline. A pilot IFC implementation detected 134 hazards, visualized all risks, generated guardrail-based protections, and produced regulation-grounded explanations. The results demonstrate a traceable, expert-governed workflow for proactive design-for-safety and BIM-based construction safety decision support.

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

### Note to Readers
Each phase in this repository contains a dedicated *README* file that provides comprehensive details, including methodology, implementation steps, dependencies, and code execution procedures.
Users are encouraged to navigate to the respective phase folders:
- 01_Fall_Hazard_Identification
- 02_Fall_Hazard_Visualization
- 03_Fall_Hazard_Prevention_and_Control
- 04_RAG_Based_LLM_Safety_Advisory
- 05_Graphical_User_Interface

and follow the instructions provided in their individual README files to successfully run and reproduce the results. These READMEs are designed to ensure clarity, reproducibility, and ease of use for all components of the system.
