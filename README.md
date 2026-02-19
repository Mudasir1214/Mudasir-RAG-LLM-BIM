# RAG-LLM-Augmented BIM for Automated Fall Hazard Identification and Prevention

## Abstract

Current Automated Rule-Checking (ARC) methods assess BIM models against safety requirements but use hard-coded rules and manual processes that are time-consuming and error-prone. Recent Large-Language Models (LLMs) with Retrieval-Augmented Generation (RAG) enable automated interpretation of regulations; however, prior studies mainly address code compliance, provide limited treatment of fall hazards, struggle with geometric reasoning, and focus on guidance over prevention. This paper proposes RAG-LLM-augmented BIM for automated fall hazard identification and prevention. Fall regulations were structured using ontology to establish geometric, semantic, and spatial relationships with BIM elements. Detected hazards were visualized using severity- and hazard-based color coding, and OSHA-compliant guardrails were installed with rationale-based advisories. Detection engine achieved 97.7% geometric success in hazard detection, with 100% visualization and guardrail placement accuracy. The pipeline showed 2.4s response time, 100% retrieval performance, and 0.985 precision. This study advances Design-for-Safety (DfS) techniques and positions RAG-LLM-augmented BIM as an enabler of construction safety management.

## Keywords
Retrieval augmented generation, Large language models, Building information modeling, Automated rule checking, Design for Safety, Fall hazards.

### Problem Statement

Construction sites experience the highest rate of fatal accidents among all industries, with falls from height accounting for approximately 33-40% of all construction fatalities globally. Traditional manual safety inspections are:
- Time-consuming and labor-intensive
- Subject to human error and inconsistency
- Conducted reactively rather than proactively during design phase
- Unable to scale across large, complex building projects

### Proposed Solution

This research implements an automated, geometry-based hazard detection pipeline that:
1. **Proactively identifies** safety hazards during the design/planning phase
2. **Quantifies risk** using regulatory threshold compliance metrics
3. **Generates structured data** for downstream visualization and mitigation planning
4. **Scales efficiently** across projects of any size or complexity
