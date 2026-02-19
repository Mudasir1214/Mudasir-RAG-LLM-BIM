#!/usr/bin/env python3
"""
llm_hazard_advisor.py
LLM-powered BIM Safety Advisor with RAG (Retrieval Augmented Generation)

This system provides intelligent analysis of your IFC hazard detection results.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
from glob import glob


# For embeddings and vector search
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("⚠️  sentence-transformers not installed. Using simpler search.")
    print("   Install with: pip install sentence-transformers")

# For LLM API calls
try:
    import openai
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️  openai package not installed.")
    print("   Install with: pip install openai")

project_root_path = Path(__file__).resolve().parents[1]

# ==========================================
# CONFIGURATION - EDIT YOUR API KEY HERE
# ==========================================
class Config:
    """Configuration for LLM system"""

    # Get API key from environment variable for security
    API_KEY = os.getenv("LLM_API_KEY", "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")

    API_BASE = os.getenv("LLM_API_BASE", "https://openrouter.ai/api/v1")
    MODEL = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")  # Working DeepSeek model 
    FINETUNED_MODEL_PATH = "llm_data/fine_tuned_model.json"

    # Paths
    KNOWLEDGE_BASE_PATH = "llm_data/knowledge_base.json"
    CONVERSATION_HISTORY = "llm_data/conversation_history.json"
    
    # RAG Parameters
    TOP_K_RESULTS = 5  # Number of relevant documents to retrieve
    MAX_CONTEXT_LENGTH = 8000  # Max tokens for context
    TEMPERATURE = 0.7
    MAX_RESPONSE_TOKENS = 1000
    
    # Embeddings model (if using sentence-transformers)
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ==========================================
# VECTOR DATABASE (Simple Implementation)
# ==========================================
class SimpleVectorDB:
    """
    Simple vector database for RAG.
    For production, consider: Pinecone, Weaviate, ChromaDB, or FAISS
    """
    
    def __init__(self):
        self.documents = []
        self.embeddings = []
        
        if EMBEDDINGS_AVAILABLE:
            print("Loading embedding model...")
            self.encoder = SentenceTransformer(Config.EMBEDDING_MODEL)
        else:
            self.encoder = None
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """Add documents to the vector database"""
        self.documents = documents
        
        if self.encoder:
            print(f"Generating embeddings for {len(documents)} documents...")
            texts = [doc['content'] for doc in documents]
            self.embeddings = self.encoder.encode(texts, show_progress_bar=True)
        else:
            # Fallback: simple keyword matching
            self.embeddings = None
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents"""
        
        if self.encoder and self.embeddings is not None:
            # Semantic search using embeddings
            query_embedding = self.encoder.encode([query])[0]
            
            # Calculate cosine similarity
            similarities = np.dot(self.embeddings, query_embedding)
            
            # Get top-k results
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                doc = self.documents[idx].copy()
                doc['relevance_score'] = float(similarities[idx])
                results.append(doc)
            
            return results
        else:
            # Fallback: keyword-based search
            return self._keyword_search(query, top_k)
    
    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Simple keyword-based search"""
        query_lower = query.lower()
        keywords = query_lower.split()
        
        scored_docs = []
        for doc in self.documents:
            content_lower = doc['content'].lower()
            score = sum(1 for kw in keywords if kw in content_lower)
            
            if score > 0:
                doc_copy = doc.copy()
                doc_copy['relevance_score'] = score
                scored_docs.append(doc_copy)
        
        # Sort by score and return top-k
        scored_docs.sort(key=lambda x: x['relevance_score'], reverse=True)
        return scored_docs[:top_k]

# ==========================================
# LLM CLIENT
# ==========================================
class LLMClient:
    """Client for LLM API calls"""
    
    def __init__(self):
        if not LLM_AVAILABLE:
            raise ImportError("OpenAI package required. Install with: pip install openai")
        
        # Initialize OpenAI client (works with DeepSeek too)
        self.client = openai.OpenAI(
            api_key=Config.API_KEY,
            base_url=Config.API_BASE
        )
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = Config.TEMPERATURE,
        max_tokens: int = Config.MAX_RESPONSE_TOKENS
    ) -> tuple:
        """Generate response from LLM and return response with token usage"""

        try:
            response = self.client.chat.completions.create(
                model=Config.MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content
            # Get actual token usage if available
            tokens_used = None
            if hasattr(response, 'usage') and response.usage:
                tokens_used = response.usage.total_tokens

            return content, tokens_used

        except Exception as e:
            error_msg = f"Error calling LLM API: {e}\n\nPlease check your API key and configuration."
            return error_msg, None

# ==========================================
# HAZARD ADVISOR SYSTEM
# ==========================================
class HazardAdvisor:
    """Main system for LLM-powered hazard analysis"""
    
    def __init__(self):
        self.vector_db = SimpleVectorDB()
        self.llm_client = None
        self.conversation_history = []
        self.current_hazards = None
        
        # Load knowledge base
        self._load_knowledge_base()
        
        # Initialize LLM if available
        if LLM_AVAILABLE:
            try:
                # Try to auto-load fine-tuned model id
                self._load_finetuned_model_override()
                self.llm_client = LLMClient()
            except Exception as e:
                print(f"Warning: Could not initialize LLM client: {e}")
        
        # Load conversation history if exists
        self._load_conversation_history()
    
    def _load_knowledge_base(self):
        """Load and index knowledge base"""
        kb_path = Path(Config.KNOWLEDGE_BASE_PATH)
        
        if not kb_path.exists():
            print(f"⚠️  Knowledge base not found: {Config.KNOWLEDGE_BASE_PATH}")
            print("   Please run prepare_llm_training_data.py first")
            self.vector_db.add_documents([])
            return
        
        with open(kb_path) as f:
            knowledge_base = json.load(f)
        
        print(f"✓ Loaded knowledge base: {len(knowledge_base)} documents")
        self.vector_db.add_documents(knowledge_base)
    
    def _load_conversation_history(self):
        """Load previous conversation"""
        hist_path = Path(Config.CONVERSATION_HISTORY)
        
        if hist_path.exists():
            with open(hist_path) as f:
                self.conversation_history = json.load(f)
    
    def _save_conversation_history(self):
        """Save conversation for context retention"""
        hist_path = Path(Config.CONVERSATION_HISTORY)
        hist_path.parent.mkdir(exist_ok=True)
        
        with open(hist_path, 'w') as f:
            json.dump(self.conversation_history, f, indent=2)

    def _load_finetuned_model_override(self):
        """If a fine-tuned model id exists on disk, override Config.MODEL."""
        try:
            p = Path(Config.FINETUNED_MODEL_PATH)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                model_id = data.get('model')
                status = data.get('status')
                if status == 'succeeded' and model_id:
                    print(f"✓ Using fine-tuned model: {model_id}")
                    os.environ['LLM_MODEL'] = model_id
                    # Also update Config.MODEL used at LLMClient init
                    Config.MODEL = model_id
        except Exception as e:
            print(f"Note: Could not load fine-tuned model id: {e}")
            
    def find_latest_hazards_file(self, pattern: str = None) -> Path:
        """
        Find the most recent hazards_detected.json file

        Args:
            pattern: Glob pattern to search (from config if None)

        Returns:
            Path to hazards file
        """
        # if pattern is None:
        #     pattern = config.HAZARDS_JSON_PATH

        matches = []

        # If pattern is set, try to find it
        if pattern:
            # Expand pattern
            full_pattern = str(project_root_path / pattern)
            matches = glob(full_pattern)
        
        # If no matches found, try alternative locations
        if not matches:    
            # Try alternative locations
            alt_patterns = [
                "/output_data/hazard_identification_results/**/hazards_detected.json",
                "/01_Fall_Hazard_Identification/hazard_identification_results/**/hazards_detected.json",
                "/hazard_identification_results/**/hazards_detected.json",
                "/hazards_detected.json",
            ]

            for alt_pattern in alt_patterns:
                alt_pattern = os.path.join(str(project_root_path), alt_pattern.lstrip("/"))

                matches = glob(alt_pattern, recursive=True)
                if matches:
                    break

        if not matches:
            raise FileNotFoundError(
                f"Could not find hazards_detected.json.\n"
                f"Please run Phase 1 first or specify the path with --hazards"
            )

        # Get most recent file
        latest = max(matches, key=os.path.getmtime)
        return Path(latest)

    
    def load_hazards(self, hazards_file: str):
        """Load new hazards file"""
        with open(hazards_file) as f:
            self.current_hazards = json.load(f)
        
        print(f"✓ Loaded {len(self.current_hazards)} hazards from {hazards_file}")
        
        # Add to context
        self.conversation_history.append({
            "role": "system",
            "content": f"User uploaded new hazard report: {len(self.current_hazards)} hazards detected. Ready to analyze."
        })
    
    def query(self, user_question: str) -> str:
        """
        Main query interface.
        Takes user question, retrieves relevant context, generates response.
        """
        
        # Import metrics tracker (optional - may not exist on all systems)
        try:
            from metrics_tracker import get_tracker
            tracker = get_tracker()
            query_data = tracker.start_query(user_question)
            has_metrics = True
        except (ImportError, Exception):
            tracker = None
            query_data = None
            has_metrics = False

        print(f"\n🔍 Searching knowledge base...")
        
        # 1. Retrieve relevant documents
        relevant_docs = self.vector_db.search(user_question, top_k=Config.TOP_K_RESULTS)
        
        # 2. Build context from retrieved documents
        context_parts = []
        for doc in relevant_docs:
            context_parts.append(f"### {doc['type'].upper()}: {doc.get('id', 'Unknown')}\n{doc['content']}")
        
        context = "\n\n".join(context_parts)
        
        # 3. Add current hazards summary if loaded
        hazards_context = ""
        if self.current_hazards:
            hazards_context = self._generate_hazards_summary()
        
        # 4. Build full prompt
        system_prompt = f"""You are an expert construction safety advisor specializing in BIM-based fall hazard detection and OSHA compliance.

You have access to:
1. Safety regulations and best practices
2. Current hazard detection report: {len(self.current_hazards) if self.current_hazards else 0} hazards

Provide detailed, actionable advice based on:
- OSHA standards
- International construction safety regulations
- BIM/IFC building model data
- Risk assessment methodologies

Be specific, practical, and prioritize worker safety.

CURRENT HAZARDS SUMMARY:
{hazards_context}

RELEVANT KNOWLEDGE:
{context}
"""
        
        # 5. Build messages for LLM
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add recent conversation history (last 5 exchanges)
        recent_history = [msg for msg in self.conversation_history if msg['role'] in ['user', 'assistant']][-10:]
        messages.extend(recent_history)
        
        # Add current question
        messages.append({"role": "user", "content": user_question})
        
        # 6. Generate response
        actual_tokens = None
        if self.llm_client:
            print("💭 Generating response...")
            response, actual_tokens = self.llm_client.generate(messages)
        else:
            response = self._fallback_response(user_question, relevant_docs)

        # 7. Save to conversation history
        self.conversation_history.append({"role": "user", "content": user_question})
        self.conversation_history.append({"role": "assistant", "content": response})
        self._save_conversation_history()

        # 8. Track metrics (if metrics tracker is available)
        if has_metrics and tracker:
            metrics = tracker.end_query(query_data, response, actual_tokens, Config.MODEL)
            print(f"⏱️  Response time: {metrics['response_time_ms']:.1f}ms")
            print(f"🎯 Tokens used: {metrics['tokens_used']:,}")
            print(f"📝 Response length: {metrics['response_length_chars']} characters")

        return response
    
    def _generate_hazards_summary(self) -> str:
        """Generate summary of current hazards"""
        if not self.current_hazards:
            return "No hazards loaded."
        
        from collections import Counter
        
        total = len(self.current_hazards)
        by_severity = Counter(h['Severity'] for h in self.current_hazards)
        by_category = Counter(h['Category'] for h in self.current_hazards)
        by_hazard = Counter(h['SpecificHazard'] for h in self.current_hazards)
        
        critical_hazards = [h for h in self.current_hazards if h['Severity'] == 'Critical'][:5]
        
        summary = f"""
Total Hazards: {total}

By Severity:
{chr(10).join(f'  - {sev}: {count}' for sev, count in by_severity.most_common())}

By Category:
{chr(10).join(f'  - {cat}: {count}' for cat, count in by_category.most_common())}

Top Hazard Types:
{chr(10).join(f'  - {haz}: {count}' for haz, count in by_hazard.most_common(5))}

Critical Hazards (showing first 5):
{chr(10).join(f'  - {h["SpecificHazard"]} at {h["DetectedValue_mm"]}mm ({h["ElementContext"].get("Element", "Unknown")})' for h in critical_hazards)}
"""
        return summary
    
    def _fallback_response(self, question: str, relevant_docs: List[Dict]) -> str:
        """Fallback response when LLM not available"""
        response = f"**Based on your question about: {question}**\n\n"
        
        if relevant_docs:
            response += "Here's relevant information from the knowledge base:\n\n"
            for doc in relevant_docs[:3]:
                response += f"### {doc['type'].upper()}\n{doc['content'][:500]}...\n\n"
        else:
            response += "No directly relevant information found. Please check the knowledge base.\n"
        
        response += "\n**Note:** LLM API not configured. Install openai package and set API key for full functionality."
        
        return response
    
    def get_conversation_history(self) -> List[Dict]:
        """Get full conversation history"""
        return self.conversation_history
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self._save_conversation_history()
        print("✓ Conversation history cleared")

# ==========================================
# COMMAND LINE INTERFACE
# ==========================================
def main():
    """Interactive CLI"""
    print("\n" + "="*80)
    print("🏗️  BIM FALL HAZARD ADVISOR - LLM System")
    print("="*80)
    print("\nInitializing system...")
    
    # Check if API key is configured
    if not Config.API_KEY:
        print("\n⚠️  WARNING: API key not configured!")
        print("   Set environment variable: export LLM_API_KEY='your-key-here'")
        print("   For Windows: set LLM_API_KEY=your-key-here")
        print("\n   System will run in demo mode with limited functionality.\n")
    
    try:
        advisor = HazardAdvisor()
    except Exception as e:
        print(f"\n❌ Error initializing system: {e}")
        return
    
    print("\n✓ System ready!")
    print("\nAvailable commands:")
    print("  load <file>     - Load a hazards JSON file")
    print("  query <text>    - Ask a question")
    print("  history         - Show conversation history")
    print("  clear           - Clear conversation history")
    print("  help            - Show example questions")
    print("\nNotes: Confusion matrices supported in training scripts (5x5 for considered hazards and 3x3 for major categories).")
    print("  exit            - Exit program")
    print("\n" + "="*80)
    
    # load hazard_detected.json fille if exists
    hazards_path = advisor.find_latest_hazards_file()
    
    if Path(hazards_path).exists():
        print(f"\n📁 Auto-loading: {hazards_path}")
        advisor.load_hazards(hazards_path)
    
    # Main loop
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if not user_input:
                continue
            
            command = user_input.split()[0].lower()
            
            if command == "exit":
                # Save metrics before exiting (if metrics tracker is available)
                try:
                    from metrics_tracker import get_tracker
                    tracker = get_tracker()
                    tracker.save_run()
                except (ImportError, Exception):
                    pass
                
                print("\nGoodbye! Stay safe! 👷")
                break
            
            elif command == "load":
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: load <filename>")
                else:
                    try:
                        advisor.load_hazards(parts[1])
                    except Exception as e:
                        print(f"Error loading file: {e}")
            
            elif command == "query":
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: query <your question>")
                else:
                    response = advisor.query(parts[1])
                    print(f"\n🤖 Advisor:\n{response}")
            
            elif command == "history":
                history = advisor.get_conversation_history()
                print(f"\nConversation History ({len(history)} messages):")
                for msg in history[-10:]:  # Last 10 messages
                    role = msg['role'].upper()
                    content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                    print(f"  [{role}] {content}")
            
            elif command == "clear":
                advisor.clear_history()
            
            elif command == "help":
                print("\n📚 Example Questions:")
                print("  - What are the top 5 critical hazards?")
                print("  - How do I fix floor opening hazards?")
                print("  - What regulations apply to my column hazards?")
                print("  - Generate an inspection checklist for openings")
                print("  - Estimate cost to fix all stairway hazards")
                print("  - What's the priority order for remediation?")
                print("  - Which hazards require immediate action?")
            
            else:
                # Treat as direct query
                response = advisor.query(user_input)
                print(f"\n🤖 Advisor:\n{response}")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'exit' to quit.")
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()