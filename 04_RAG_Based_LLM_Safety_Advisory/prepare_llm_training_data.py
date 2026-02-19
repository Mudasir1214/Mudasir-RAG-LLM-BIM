#!/usr/bin/env python3
"""
prepare_llm_training_data.py
Prepares your hazard data for LLM training/fine-tuning

Creates structured datasets for:
1. Few-shot examples
2. Fine-tuning (if needed)
3. RAG knowledge base
4. Evaluation sets
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ==========================================
# 1. CREATE KNOWLEDGE BASE FOR RAG
# ==========================================
def create_rag_knowledge_base(hazards_json_path):
    """
    Creates a structured knowledge base from your regulations and hazards.
    This will be used for Retrieval Augmented Generation (RAG).
    """
    
    # Load your hazards
    with open(hazards_json_path) as f:
        hazards = json.load(f)
    
    # Your OSHA regulations (from your code)
    regulations = {
        "FallFromHeight": {
            "OntologyID": "FH_001",
            "Category": "Elevated work hazards",
            "Regulation": "JGJ80-2016, HKLD",
            "Threshold_mm": 2000,
            "Description": "Workers at risk of falling from heights > 2m",
            "Prevention": [
                "Install guardrails (min 1.1m height)",
                "Use fall arrest systems",
                "Implement safety nets",
                "Provide proper access equipment"
            ],
            "Inspection_Points": [
                "Check railing height and strength",
                "Verify anchor points for fall arrest",
                "Inspect working surface stability",
                "Ensure proper edge protection"
            ]
        },
        "UnprotectedSidesAndEdges": {
            "OntologyID": "FH_002",
            "Category": "Elevated work hazards",
            "Regulation": "Reg. 38B, CSSR Part VA",
            "Threshold_mm": 1800,
            "Description": "Unprotected edges at heights > 1.8m",
            "Prevention": [
                "Install perimeter guardrails",
                "Use warning lines and safety monitors",
                "Implement controlled access zones",
                "Provide personal fall arrest systems"
            ],
            "Inspection_Points": [
                "Check guardrail installation (top rail 1.1m)",
                "Verify mid-rail at 0.5m",
                "Inspect toe boards (100mm minimum)",
                "Check for gaps > 500mm"
            ]
        },
        "FloorOpening": {
            "OntologyID": "FH_003",
            "Category": "Opening hazards",
            "Regulation": "GB10000-88",
            "Threshold_mm": 400,
            "Description": "Uncovered holes in floors pose fall hazards",
            "Prevention": [
                "Cover openings with rated materials",
                "Mark covers clearly",
                "Install guardrails around large openings",
                "Use safety nets below openings"
            ],
            "Inspection_Points": [
                "Verify cover strength (2x expected load)",
                "Check cover securing mechanism",
                "Ensure proper warning signage",
                "Inspect for new openings daily"
            ]
        },
        "WallOpening": {
            "OntologyID": "FH_003",
            "Category": "Opening hazards",
            "Regulation": "GB10000-88",
            "Threshold_mm": 400,
            "Description": "Wall openings for windows/doors without protection",
            "Prevention": [
                "Install temporary guardrails",
                "Use barrier systems until permanent fixtures installed",
                "Implement work positioning systems",
                "Mark danger zones clearly"
            ],
            "Inspection_Points": [
                "Check barrier strength",
                "Verify proper height (1.1m)",
                "Ensure bottom rail at 0.5m",
                "Inspect daily before work"
            ]
        },
        "RoofOpening": {
            "OntologyID": "FH_003",
            "Category": "Opening hazards",
            "Regulation": "SSA-01/2022",
            "Threshold_mm": 400,
            "Description": "Roof openings and skylights without protection",
            "Prevention": [
                "Install covers or guardrails around skylights/roof penetrations",
                "Use safety nets where feasible",
                "Clearly mark and secure covers"
            ],
            "Inspection_Points": [
                "Cover integrity and rating",
                "Proper securing of covers",
                "Warning signage present"
            ]
        },
        "LeadingEdges": {
            "OntologyID": "FH_002",
            "Category": "Elevated work hazards",
            "Regulation": "SSA-02/2021",
            "Threshold_mm": 2000,
            "Description": "Work near unfinished or unprotected edges",
            "Prevention": [
                "Guardrail systems at leading edges",
                "Controlled access zones",
                "Personal fall arrest systems"
            ],
            "Inspection_Points": [
                "Edge protection present",
                "Access control signage",
                "Anchorage points in place"
            ]
        },
        "Scaffold": {
            "OntologyID": "FH_004",
            "Category": "Access hazards",
            "Regulation": "Reg. 38C-F, CSSR Part VA",
            "Threshold_mm": 3000,
            "Description": "Work on suspended or supported scaffolds",
            "Prevention": [
                "Install complete guardrail systems",
                "Ensure proper base plates and ties",
                "Daily inspection by competent person"
            ],
            "Inspection_Points": [
                "Guardrail height",
                "Decking completeness",
                "Stability and anchorage"
            ]
        },
        "Ladder": {
            "OntologyID": "FH_005",
            "Category": "Access hazards",
            "Regulation": "Reg. 38C-F, CSSR Part VA",
            "Threshold_mm": 915,
            "Description": "Use of portable ladders",
            "Prevention": [
                "Set correct angle (4:1)",
                "Extend 1m above landing",
                "Inspect ladders before use"
            ],
            "Inspection_Points": [
                "Angle and securement",
                "Top extension",
                "Rung condition"
            ]
        },
        "Stairway": {
            "OntologyID": "FH_006",
            "Category": "Access hazards",
            "Regulation": "Reg. 38C-F, CSSR Part VA",
            "Threshold_mm": 760,
            "Description": "Stairways without adequate safety measures",
            "Prevention": [
                "Install handrails",
                "Non-slip treads",
                "Adequate lighting"
            ],
            "Inspection_Points": [
                "Handrail presence and height",
                "Tread condition",
                "Illumination"
            ]
        },
        "Excavation": {
            "OntologyID": "FH_001",
            "Category": "Excavation hazards",
            "Regulation": "Reg. 39-41, CSSR Part VI & VII",
            "Threshold_mm": 2000,
            "Description": "Open pits and trenches without edge protection",
            "Prevention": [
                "Edge protection and barricades",
                "Safe access/egress",
                "Shoring or sloping as required"
            ],
            "Inspection_Points": [
                "Edge protection",
                "Soil stability",
                "Water accumulation"
            ]
        }
    }
    
    # Create structured documents for RAG
    knowledge_base = []
    
    # 1. Regulation documents
    for hazard_type, reg_info in regulations.items():
        doc = {
            "id": f"REG_{reg_info['OntologyID']}",
            "type": "regulation",
            "hazard_type": hazard_type,
            "content": f"""
REGULATION: {hazard_type}
Ontology ID: {reg_info['OntologyID']}
Category: {reg_info['Category']}
Standard: {reg_info['Regulation']}
Threshold: {reg_info['Threshold_mm']}mm

Description:
{reg_info['Description']}

Prevention Measures:
{chr(10).join(f"- {measure}" for measure in reg_info['Prevention'])}

Inspection Points:
{chr(10).join(f"- {point}" for point in reg_info['Inspection_Points'])}
""",
            "metadata": reg_info
        }
        knowledge_base.append(doc)
    
    # 2. Best practices document
    best_practices = {
        "id": "BEST_PRACTICES_001",
        "type": "best_practice",
        "content": """
CONSTRUCTION SITE FALL PREVENTION BEST PRACTICES

1. Hierarchy of Controls (Apply in Order):
   - Elimination: Remove the hazard (redesign, prefabrication)
   - Substitution: Replace with safer process
   - Engineering Controls: Guardrails, covers, safety nets
   - Administrative Controls: Training, procedures, signage
   - PPE: Harnesses, helmets (last resort)

2. Daily Site Inspection Checklist:
   - Walk perimeter, check all guardrails
   - Inspect floor openings and covers
   - Verify ladder conditions and placement
   - Check scaffold integrity
   - Review weather conditions affecting safety

3. Common Mistakes to Avoid:
   - Assuming previous inspections are still valid
   - Using damaged or incorrect PPE
   - Inadequate edge protection on new floors
   - Missing covers on small openings
   - Improper scaffold assembly

4. Emergency Response:
   - Post rescue plan visibly
   - Train workers on fall rescue procedures
   - Maintain rescue equipment in accessible location
   - Conduct quarterly rescue drills
"""
    }
    knowledge_base.append(best_practices)
    
    # 3. Case studies from your actual detected hazards
    hazard_summary = defaultdict(list)
    for h in hazards:
        hazard_summary[h['SpecificHazard']].append(h)
    
    for hazard_type, examples in hazard_summary.items():
        if len(examples) > 0:
            case_study = {
                "id": f"CASE_{hazard_type.upper().replace(' ', '_')}",
                "type": "case_study",
                "hazard_type": hazard_type,
                "content": f"""
DETECTED HAZARDS: {hazard_type}
Total Instances: {len(examples)}

Severity Distribution:
{_get_severity_dist(examples)}

Common Characteristics:
- Average detected value: {sum(e['DetectedValue_mm'] for e in examples) / len(examples):.1f}mm
- Threshold: {examples[0]['Threshold_mm']}mm
- Regulation: {examples[0]['Regulation']}

Recommended Actions:
1. Prioritize {len([e for e in examples if e['Severity'] == 'Critical'])} Critical severity items
2. {_get_recommendations(hazard_type, examples)}

Example Locations:
{chr(10).join(f"- {e['ElementContext'].get('Element', 'Unknown')}: {e['DetectedValue_mm']}mm" for e in examples[:5])}
""",
                "metadata": {
                    "count": len(examples),
                    "severities": {s: len([e for e in examples if e['Severity'] == s]) for s in ['Low', 'Medium', 'High', 'Critical']}
                }
            }
            knowledge_base.append(case_study)
    
    # Save knowledge base
    output_dir = Path("llm_data")
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "knowledge_base.json", 'w') as f:
        json.dump(knowledge_base, f, indent=2)
    
    print(f"✓ Created knowledge base: {len(knowledge_base)} documents")
    return knowledge_base

def _get_severity_dist(examples):
    severities = defaultdict(int)
    for e in examples:
        severities[e['Severity']] += 1
    return "\n".join(f"- {sev}: {count}" for sev, count in severities.items())

def _get_recommendations(hazard_type, examples):
    if "Floor opening" in hazard_type:
        return "Install approved covers or guardrails around all openings"
    elif "Wall opening" in hazard_type:
        return "Install temporary barriers until permanent fixtures are in place"
    elif "Unprotected" in hazard_type:
        return "Install perimeter guardrails meeting minimum height requirements"
    elif "Column" in hazard_type:
        return "Install edge protection at exposed column tops"
    return "Conduct detailed site assessment for mitigation strategies"

# ==========================================
# 2. CREATE FEW-SHOT EXAMPLES
# ==========================================
def create_few_shot_examples(hazards_json_path):
    """
    Creates few-shot learning examples for prompt engineering.
    These show the LLM how to analyze hazards and give recommendations.
    """
    
    with open(hazards_json_path) as f:
        hazards = json.load(f)
    
    # Select diverse examples
    examples = []
    
    # Example 1: Critical floor opening
    floor_opening = next((h for h in hazards if h['SpecificHazard'] == 'Floor openings (Horizontal)' and h['Severity'] == 'Critical'), None)
    if floor_opening:
        examples.append({
            "role": "user",
            "content": f"Analyze this hazard:\n{json.dumps(floor_opening, indent=2)}"
        })
        examples.append({
            "role": "assistant",
            "content": f"""HAZARD ANALYSIS:

**Hazard Type:** Floor Opening (Horizontal)
**Severity:** {floor_opening['Severity']}
**Location:** {floor_opening['ElementContext'].get('Opening', 'Unknown')}
**Dimensions:** {floor_opening['ElementContext'].get('Width_mm')}mm x {floor_opening['ElementContext'].get('Depth_mm')}mm

**Risk Assessment:**
This is a CRITICAL hazard. The opening ({floor_opening['DetectedValue_mm']:.1f}mm) significantly exceeds the {floor_opening['Threshold_mm']}mm threshold set by {floor_opening['Regulation']}.

**Immediate Actions Required:**
1. **PRIORITY 1 - IMMEDIATE:** Barricade the area with physical barriers
2. Install temporary covers rated for 2x expected load (min 450kg/m²)
3. Mark covers with "HOLE" or "COVER - DO NOT REMOVE"
4. Implement permit system before cover removal

**Long-term Solutions:**
- Install permanent guardrails (1.1m height) if opening remains
- Consider prefabricated cover systems for frequently accessed openings
- Train workers on opening hazard recognition

**Inspection Schedule:**
- Daily visual inspection before work begins
- Weekly detailed inspection of cover integrity
- Document all inspections

**Estimated Risk Reduction:** Installing proper cover reduces fall risk by 95%"""
        })
    
    # Example 2: Fall from height (FFH) slab without protection
    ffh = next((h for h in hazards if h['SpecificHazard'] == 'Fall from height'), None)
    if ffh:
        examples.append({
            "role": "user",
            "content": f"What should I check for this fall-from-height hazard?\n{json.dumps(ffh, indent=2)}"
        })
        examples.append({
            "role": "assistant",
            "content": f"""INSPECTION CHECKLIST:

**Element:** {ffh['ElementContext'].get('Element', 'Unknown')}
**Elevation:** {ffh['DetectedValue_mm']:.1f}mm ({ffh['DetectedValue_mm']/1000:.1f}m)
**Fall Level:** {ffh.get('FallLevel', 'Unknown')}

□ Perimeter Protection:
  - Guardrails installed (top rail 1.1m, mid-rail 0.5m, toe board 100mm)
  - No gaps > 500mm, posts ≤ 2.4m spacing

□ Access Control:
  - Warning signage and barricades
  - Controlled access zones near edges

□ PPE:
  - Fall arrest systems available and inspected
  - Anchorage points rated and verified

□ Documentation:
  - Included in daily toolbox talk
  - Rescue plan available and briefed"""
        })
    
    # Example 3: Multiple stair hazards
    stairs = [h for h in hazards if h['SpecificHazard'] == 'Stairways']
    if len(stairs) > 1:
        examples.append({
            "role": "user",
            "content": f"I have {len(stairs)} stairways without adequate protection. What's the priority order?"
        })
        examples.append({
            "role": "assistant",
            "content": f"""PRIORITY RANKING FOR STAIRWAY HAZARDS:

**Found:** {len(stairs)} unprotected stairways

**Priority Ranking Criteria:**
1. Stair height (higher = more urgent)
2. Traffic frequency
3. Proximity to other hazards
4. Weather exposure

**Recommended Action Sequence:**

Week 1 - Immediate (Days 1-3):
- Install temporary handrails on all stairs (rope/cable minimum)
- Post warning signs at stair entrances
- Implement mandatory three-point contact rule
- Conduct emergency toolbox talk

Week 2 - Permanent Solutions (Days 4-7):
- Prioritize stairs with height > 3m first
- Install OSHA-compliant handrails (38mm diameter, 1.8m spacing)
- Add non-slip treads if needed
- Improve lighting at stairs

Week 3 - Verification:
- Final inspection of all installations
- Update site safety plan
- Train workers on proper stair use
- Schedule monthly re-inspection

**Budget Estimate:**
- Temporary measures: $50-100 per stair
- Permanent handrails: $300-600 per stair
- Total for {len(stairs)} stairs: ${len(stairs) * 400}-{len(stairs) * 700}

**Timeline:** 2-3 weeks for full compliance"""
        })
    
    # Save examples
    output_dir = Path("llm_data")
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "few_shot_examples.json", 'w') as f:
        json.dump(examples, f, indent=2)
    
    print(f"✓ Created {len(examples)} few-shot examples")
    return examples

# ==========================================
# 3. CREATE FINE-TUNING DATASET (Optional)
# ==========================================
def create_finetuning_dataset(hazards_json_path):
    """
    Creates a dataset in OpenAI/DeepSeek fine-tuning format.
    Only use this if you plan to do actual fine-tuning.
    """
    
    with open(hazards_json_path) as f:
        hazards = json.load(f)
    
    # Create training examples in JSONL format
    training_data = []
    
    for hazard in hazards:
        # Create different types of queries for each hazard
        
        # Query 1: Analysis request
        training_data.append({
            "messages": [
                {
                    "role": "system",
                    "content": "You are a construction safety expert specializing in BIM-based fall hazard analysis. Provide detailed, actionable safety recommendations based on OSHA and international construction safety standards."
                },
                {
                    "role": "user",
                    "content": f"Analyze this detected hazard:\n{json.dumps(hazard, indent=2)}"
                },
                {
                    "role": "assistant",
                    "content": generate_analysis_response(hazard)
                }
            ]
        })
        
        # Query 2: Recommendations
        training_data.append({
            "messages": [
                {
                    "role": "system",
                    "content": "You are a construction safety expert specializing in BIM-based fall hazard analysis. Provide detailed, actionable safety recommendations based on OSHA and international construction safety standards."
                },
                {
                    "role": "user",
                    "content": f"What are the top 3 recommendations for: {hazard['SpecificHazard']} at {hazard['DetectedValue_mm']}mm?"
                },
                {
                    "role": "assistant",
                    "content": generate_recommendations(hazard)
                }
            ]
        })
    
    # Save in JSONL format
    output_dir = Path("llm_data")
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "finetuning_data.jsonl", 'w') as f:
        for item in training_data:
            f.write(json.dumps(item) + '\n')
    
    print(f"✓ Created {len(training_data)} fine-tuning examples")
    return training_data

def generate_analysis_response(hazard):
    """Generate a realistic safety analysis response"""
    severity_actions = {
        "Critical": "IMMEDIATE ACTION REQUIRED",
        "High": "Action required within 24 hours",
        "Medium": "Action required within 1 week",
        "Low": "Monitor and plan remediation"
    }
    
    return f"""**{severity_actions.get(hazard['Severity'], 'Review required')}**

Hazard: {hazard['SpecificHazard']}
Severity: {hazard['Severity']}
Detected: {hazard['DetectedValue_mm']}mm (Threshold: {hazard['Threshold_mm']}mm)
Regulation: {hazard['Regulation']}

Risk: {hazard['Cause']}

Immediate Steps:
1. Barricade the hazard area
2. Post warning signage
3. Brief workers in daily safety meeting
4. Implement interim protection measures

{get_specific_recommendations(hazard['SpecificHazard'])}"""

def generate_recommendations(hazard):
    """Generate top recommendations"""
    return f"""Top 3 Recommendations for {hazard['SpecificHazard']}:

1. **Install Primary Protection**
   {get_primary_protection(hazard['SpecificHazard'])}
   
2. **Implement Administrative Controls**
   - Update site safety plan
   - Conduct targeted safety training
   - Implement permit-to-work system
   
3. **Monitor and Verify**
   - Daily pre-shift inspections
   - Weekly detailed audits
   - Monthly management review"""

def get_specific_recommendations(hazard_type):
    recommendations = {
        "Floor openings (Horizontal)": """
Permanent Solution:
- Install approved covers (min 450kg/m² rating)
- OR install guardrails (1.1m height) around opening
- Mark clearly: "DANGER - HOLE" or "COVER - DO NOT REMOVE"
- Secure covers to prevent displacement""",
        
        "Wall openings (Vertical)": """
Permanent Solution:
- Install temporary guardrails until permanent fixtures
- Use mid-rail at 0.5m and toe board at 100mm
- Consider mesh barriers for large openings
- Inspect daily before work commences""",
        
        "Unprotected sides and edges": """
Permanent Solution:
- Install perimeter guardrails per OSHA 1926.502
- Top rail: 1.1m, Mid-rail: 0.5-0.6m, Toe board: 100mm
- Ensure posts spaced max 2.4m
- Guardrails must withstand 890N force"""
    }
    return recommendations.get(hazard_type, "Consult safety engineer for specific solution")

def get_primary_protection(hazard_type):
    if "Floor opening" in hazard_type:
        return "Install approved covers or guardrail system around opening"
    elif "Wall opening" in hazard_type:
        return "Install temporary barrier system meeting 890N force requirement"
    elif "edge" in hazard_type.lower() or "Column" in hazard_type:
        return "Install perimeter guardrail system (top rail 1.1m, mid-rail 0.5m)"
    elif "Stair" in hazard_type:
        return "Install handrails both sides, 38mm diameter, 1.8m max span"
    return "Implement appropriate fall protection system per regulations"

# ==========================================
# 4. CREATE EVALUATION SET
# ==========================================
def create_evaluation_set(hazards_json_path):
    """
    Creates test questions to evaluate LLM performance.
    Use this to measure if your LLM setup is working well.
    """
    
    eval_questions = [
        {
            "question": "What are the top 5 most critical hazards in my latest report?",
            "expected_topics": ["Critical severity", "Floor openings", "Column heights", "Prioritization"]
        },
        {
            "question": "How much would it cost to fix all stairway hazards?",
            "expected_topics": ["Budget estimate", "Stair count", "Material costs", "Labor"]
        },
        {
            "question": "Which regulations apply to the detected column hazards?",
            "expected_topics": ["Reg. 38B", "CSSR Part VA", "1800mm threshold"]
        },
        {
            "question": "Generate an inspection checklist for floor openings",
            "expected_topics": ["Cover strength", "Signage", "Securing", "Daily inspection"]
        },
        {
            "question": "What fall level classification applies to hazards at 12m height?",
            "expected_topics": ["High-level fall", "4.5m threshold", "Increased risk"]
        }
    ]
    
    output_dir = Path("llm_data")
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "evaluation_questions.json", 'w') as f:
        json.dump(eval_questions, f, indent=2)
    
    print(f"✓ Created {len(eval_questions)} evaluation questions")
    return eval_questions

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    """Main execution"""
    print("\n" + "="*60)
    print("LLM TRAINING DATA PREPARATION")
    print("="*60)
    
    # Path to your hazards file
    hazards_file = "../output_data/hazard_identification_results/run_20260206_133751/hazards_detected.json"
    
    if not Path(hazards_file).exists():
        print(f"❌ Error: {hazards_file} not found!")
        print("Please run your IFC detection script first.")
        return
    
    print(f"\n📁 Processing: {hazards_file}")
    
    # Create all datasets
    print("\n[1/4] Creating RAG knowledge base...")
    knowledge_base = create_rag_knowledge_base(hazards_file)
    
    print("\n[2/4] Creating few-shot examples...")
    few_shot = create_few_shot_examples(hazards_file)
    
    print("\n[3/4] Creating fine-tuning dataset...")
    finetuning = create_finetuning_dataset(hazards_file)
    
    print("\n[4/4] Creating evaluation set...")
    evaluation = create_evaluation_set(hazards_file)
    
    print("\n" + "="*60)
    print("✅ DATA PREPARATION COMPLETE!")
    print("="*60)
    print("\nGenerated files in 'llm_data/' directory:")
    print("  • knowledge_base.json - For RAG system")
    print("  • few_shot_examples.json - For prompt engineering")
    print("  • finetuning_data.jsonl - For model fine-tuning")
    print("  • evaluation_questions.json - For testing")
    print("\nNext steps:")
    print("  1. Review generated files")
    print("\nYou can now run: python llm_hazard_advisor.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()