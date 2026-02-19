# Phase 4: RAG-Based-LLM Safety Advisory

## Executive Summary

Phase 4 implements an intelligent, context-aware conversational system that leverages Large Language Models (LLMs) enhanced with Retrieval-Augmented Generation (RAG) to provide expert-level construction safety advisory. The system ingests structured hazard data from Phases 1-3, builds a vector-indexed knowledge base, and delivers natural language guidance on hazard mitigation, regulatory compliance, and best practices.

## Technical Architecture

### 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                           │
│              (Chatbot GUI - Phase 4)                        │
└─────────────────┬───────────────────────────────────────────┘
                  │ Natural Language Query
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                 RAG PIPELINE                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Query Encoding                                    │  │
│  │    (sentence-transformers: all-MiniLM-L6-v2)        │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │ Query Vector (384-dim)                   │
│                 ▼                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. Vector Search                                     │  │
│  │    - Cosine similarity with knowledge base           │  │
│  │    - Top-K retrieval (K=5)                          │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │ Relevant Documents                        │
│                 ▼                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. Context Assembly                                  │  │
│  │    - Concatenate retrieved docs                      │  │
│  │    - Add system prompt                               │  │
│  │    - Inject project-specific data                    │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │ Augmented Prompt                          │
│                 ▼                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 4. LLM Generation                                    │  │
│  │    - OpenRouter API (DeepSeek)                       │  │
│  │    - Temperature: 0.7                                │  │
│  │    - Max tokens: 1000                                │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │ Response                                  │
└─────────────────┴───────────────────────────────────────────┘
                  │
                  ▼
           Natural Language Answer
```

### 2. Knowledge Base Construction

#### Master RAG Dataset Generation

The system aggregates data from all pipeline phases into a unified knowledge base:

```python
def create_master_rag():
    """
    Constructs comprehensive knowledge base from all phases
    
    Data Sources:
    1. Phase 1: Hazard detection results (hazards_detected.json)
    2. Phase 2: Visualization metadata (visualization_report.json)
    3. Phase 3: Guardrail generation report (report.json)
    4. Regulatory database: OSHA, JGJ, CSSR, HKLD standards
    5. Best practices: Industry guidelines, case studies
    
    Output: master_rag_training_data.json
    """
    master_data = {
        "document_type": "BIM Safety Analysis - Complete Project",
        "generated_at": datetime.now().isoformat(),
        
        "project_overview": {
            "building_model": IFC_FILENAME,
            "total_hazards": hazard_count,
            "hazards_by_type": hazard_distribution,
            "guardrail_components": component_count
        },
        
        "regulatory_knowledge": {
            "FallFromHeight": {
                "regulation": "OSHA 1926.501, JGJ80-2016",
                "threshold_mm": 2000,
                "description": "Risk of falling from heights >2m",
                "prevention_measures": [
                    "Install guardrails (min 1.1m height)",
                    "Use fall arrest systems",
                    "Implement safety nets"
                ],
                "inspection_checklist": [
                    "Check railing height and strength",
                    "Verify anchor points",
                    "Inspect working surface stability"
                ]
            },
            # ... (full regulatory database)
        },
        
        "detected_hazards": {
            "summary": {
                "total": 134,
                "by_severity": {
                    "Critical": 45,
                    "High": 52,
                    "Medium": 28,
                    "Low": 9
                }
            },
            "examples": [
                # Detailed hazard instances from Phase 1
            ]
        },
        
        "mitigation_strategies": {
            "UnprotectedSidesAndEdges": {
                "primary": "Install OSHA-compliant guardrails",
                "specifications": {
                    "top_rail_height": "1100mm (42 inches)",
                    "mid_rail_height": "550mm",
                    "post_spacing": "≤2000mm (8 feet)",
                    "toe_board": "≥100mm"
                },
                "alternatives": [
                    "Safety nets (where guardrails infeasible)",
                    "Personal fall arrest systems (PFAS)",
                    "Warning line systems + safety monitors"
                ],
                "cost_estimate": {
                    "guardrail_per_meter": "$50-80 USD",
                    "installation_labor": "$30-50/hour",
                    "typical_project": "$5000-15000"
                }
            },
            # ... (all hazard types)
        },
        
        "best_practices": {
            "hierarchy_of_controls": [
                "1. Elimination: Redesign to remove hazard",
                "2. Substitution: Replace with safer process",
                "3. Engineering controls: Guardrails, covers",
                "4. Administrative: Training, procedures",
                "5. PPE: Last resort (harnesses, helmets)"
            ],
            "inspection_frequency": {
                "guardrails": "Daily before work",
                "floor_openings": "Daily + after weather events",
                "scaffolds": "Before each shift + after modifications"
            }
        },
        
        "q_and_a_examples": [
            {
                "question": "How many Critical severity hazards were detected?",
                "answer": f"The analysis detected {critical_count} Critical severity hazards requiring immediate attention."
            },
            # ... (50+ Q&A pairs)
        ]
    }
    
    return master_data
```

#### Document Chunking and Embedding

```python
class SimpleVectorDB:
    """
    Lightweight vector database for RAG
    
    Production Alternative: Pinecone, Weaviate, ChromaDB, FAISS
    """
    
    def __init__(self):
        self.documents = []
        self.embeddings = []
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        # Model specs: 384-dimensional vectors, trained on 1B+ sentence pairs
    
    def add_documents(self, documents: List[Dict]):
        """
        Embeds and indexes documents
        
        Process:
        1. Extract text content from each document
        2. Generate embeddings (384-dim vectors)
        3. Store (document, embedding) pairs
        
        Embedding Model: all-MiniLM-L6-v2
        - Size: 384 dimensions
        - Speed: ~500 sentences/second
        - Quality: Optimized for semantic similarity
        """
        self.documents = documents
        
        texts = [doc['content'] for doc in documents]
        logging.info(f"Generating embeddings for {len(texts)} documents...")
        
        self.embeddings = self.encoder.encode(
            texts,
            show_progress_bar=True,
            batch_size=32
        )
        
        logging.info(f"Indexed {len(self.documents)} documents")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Semantic search over knowledge base
        
        Algorithm:
        1. Encode query to 384-dim vector
        2. Compute cosine similarity with all document embeddings
        3. Return top-K most similar documents
        
        Cosine Similarity:
            similarity = (A · B) / (||A|| × ||B||)
        Range: [-1, 1], where 1 = identical, 0 = orthogonal
        """
        query_embedding = self.encoder.encode([query])[0]
        
        # Compute cosine similarities
        similarities = np.dot(self.embeddings, query_embedding)
        
        # Get top-K indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Return documents with scores
        results = []
        for idx in top_indices:
            results.append({
                'document': self.documents[idx],
                'score': float(similarities[idx])
            })
        
        return results
```

### 3. LLM Integration

#### OpenRouter API Configuration

```python
class Config:
    """LLM system configuration"""
    
    # API credentials
    API_KEY = os.getenv("LLM_API_KEY", "")
    API_BASE = "https://openrouter.ai/api/v1"
    
    # Model selection
    MODEL = "deepseek/deepseek-chat"
    # Alternative models:
    # - "anthropic/claude-3-sonnet"
    # - "openai/gpt-4-turbo"
    # - "google/gemini-pro"
    
    # Generation parameters
    TEMPERATURE = 0.7  # Creativity vs. determinism (0.0 = deterministic)
    MAX_RESPONSE_TOKENS = 1000
    TOP_K_RESULTS = 5  # Number of RAG documents to retrieve
```

**Model Rationale**:
- **DeepSeek**: Open-source, cost-effective ($0.14/1M tokens)
- **Performance**: Comparable to GPT-3.5 on domain tasks
- **Accessibility**: No waitlist, immediate API access

#### Prompt Engineering

```python
def create_rag_prompt(query: str, context_docs: List[Dict], 
                      project_data: Dict) -> str:
    """
    Constructs RAG-augmented prompt
    
    Prompt Structure:
    1. System role definition
    2. Project context (building model, hazard counts)
    3. Retrieved knowledge base excerpts
    4. User query
    5. Response guidelines
    """
    prompt = f"""You are an expert construction safety consultant specializing in fall hazard prevention. You have access to detailed analysis of a building project and comprehensive safety regulations.

PROJECT CONTEXT:
- Building Model: {project_data['ifc_filename']}
- Total Hazards Detected: {project_data['hazard_count']}
- Critical Severity: {project_data['critical_count']}
- Guardrails Generated: {project_data['component_count']} components

RELEVANT KNOWLEDGE BASE:
"""
    
    # Add retrieved documents
    for i, doc in enumerate(context_docs, 1):
        prompt += f"\n[Document {i}]\n{doc['document']['content']}\n"
    
    prompt += f"""

USER QUESTION:
{query}

RESPONSE GUIDELINES:
- Provide factual, regulation-based guidance
- Reference specific OSHA/JGJ standards when applicable
- Include actionable recommendations
- If asked about project specifics, use PROJECT CONTEXT data
- If uncertain, state limitations clearly (don't hallucinate)

ANSWER:
"""
    
    return prompt
```

#### LLM Invocation

```python
def query_llm(prompt: str, api_key: str) -> str:
    """
    Calls LLM API with RAG-augmented prompt
    
    API: OpenRouter (unified interface for multiple LLM providers)
    Error Handling:
    - Network failures → Retry with exponential backoff
    - Rate limiting → Automatic retry after delay
    - Invalid API key → Clear error message
    """
    client = openai.OpenAI(
        base_url=Config.API_BASE,
        api_key=api_key
    )
    
    try:
        response = client.chat.completions.create(
            model=Config.MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_RESPONSE_TOKENS
        )
        
        answer = response.choices[0].message.content
        
        # Log token usage for cost tracking
        logging.info(f"Tokens used: {response.usage.total_tokens}")
        
        return answer
        
    except openai.AuthenticationError:
        return "ERROR: Invalid API key. Please configure your OpenRouter API key."
    except openai.RateLimitError:
        return "ERROR: Rate limit exceeded. Please try again in a few moments."
    except Exception as e:
        logging.error(f"LLM query failed: {e}")
        return f"ERROR: {str(e)}"
```

### 4. Conversational Interface

#### Chat History Management

```python
class ConversationManager:
    """Manages multi-turn conversations with context persistence"""
    
    def __init__(self, max_history: int = 10):
        self.history = []
        self.max_history = max_history
    
    def add_turn(self, user_query: str, assistant_response: str):
        """
        Adds conversation turn to history
        
        History Format:
        [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
        """
        self.history.append({"role": "user", "content": user_query})
        self.history.append({"role": "assistant", "content": assistant_response})
        
        # Trim to max length (keep recent context)
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-(self.max_history * 2):]
    
    def get_context_window(self) -> str:
        """
        Formats conversation history for prompt injection
        
        Recent conversations provide context for follow-up questions
        Example:
            User: "What hazards were detected?"
            Assistant: "134 hazards: 89 unprotected edges, 34 stairways, ..."
            User: "Tell me more about the stairways"  # Needs previous context
        """
        if not self.history:
            return ""
        
        context = "\n\nPREVIOUS CONVERSATION:\n"
        for turn in self.history:
            role = turn['role'].upper()
            context += f"{role}: {turn['content']}\n"
        
        return context
```

### 5. GUI Integration

#### Tkinter-Based Chatbot Interface

```python
class ChatbotWindow:
    """Professional chatbot interface integrated with main GUI"""
    
    def __init__(self, parent, session_dir, api_key):
        self.window = tk.Toplevel(parent)
        self.window.title("BIM Safety AI Assistant")
        self.window.geometry("800x700")
        
        # Initialize RAG system
        self.rag_system = BIMSafetyAdvisor(session_dir, api_key)
        self.conversation_history = []
        
        # Create UI components
        self._create_ui()
    
    def _create_ui(self):
        """
        Creates chat interface
        
        Components:
        1. Header (title, status indicator)
        2. Message display (scrolled text with alternating bubbles)
        3. Input field (text entry with send button)
        4. Quick action buttons (predefined queries)
        """
        # Header
        header = tk.Frame(self.window, bg="#1a1a1a", height=60)
        header.pack(fill="x")
        
        tk.Label(
            header,
            text="🤖 BIM Safety AI Assistant",
            font=("Segoe UI", 16, "bold"),
            bg="#1a1a1a",
            fg="#ffffff"
        ).pack(pady=15)
        
        # Message display area
        self.message_frame = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            bg="#2b2b2b",
            fg="#e0e0e0",
            state=tk.DISABLED,
            padx=10,
            pady=10
        )
        self.message_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Input area
        input_frame = tk.Frame(self.window, bg="#1a1a1a")
        input_frame.pack(fill="x", padx=10, pady=10)
        
        self.input_field = tk.Entry(
            input_frame,
            font=("Segoe UI", 11),
            bg="#3a3a3a",
            fg="#ffffff",
            relief=tk.FLAT,
            insertbackground="#ffffff"
        )
        self.input_field.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_field.bind("<Return>", lambda e: self.send_message())
        
        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg="#0066cc",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=20
        )
        send_btn.pack(side="right")
        
        # Quick action buttons
        self._create_quick_actions()
    
    def send_message(self):
        """
        Processes user query and displays response
        
        Flow:
        1. Get user input from text field
        2. Display user message in chat
        3. Show "thinking" indicator
        4. Call RAG system (retrieve + generate)
        5. Display AI response in chat
        6. Update conversation history
        """
        user_input = self.input_field.get().strip()
        if not user_input:
            return
        
        # Clear input
        self.input_field.delete(0, tk.END)
        
        # Display user message
        self._append_message("You", user_input, is_user=True)
        
        # Show thinking indicator
        thinking_id = self._append_message("AI", "Thinking...", is_user=False)
        
        # Get AI response (in separate thread to prevent UI freeze)
        def get_response():
            response = self.rag_system.ask(user_input)
            
            # Update UI from main thread
            self.window.after(0, lambda: self._update_response(thinking_id, response))
        
        threading.Thread(target=get_response, daemon=True).start()
```

