"""
Chatbot Interface for BIM Safety Analysis System
Production-grade LLM-powered Q&A window using DeepSeek and RAG
"""

import os
import sys
import json
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading

from gui_config import *


class ChatbotWindow:
    """Production-grade chatbot window for LLM-powered safety advisory"""

    def __init__(self, parent, session_dir: Path, api_key: str):
        self.parent = parent
        self.session_dir = session_dir
        self.api_key = api_key
        self.advisor = None
        self.conversation_history = []
        self.is_waiting = False

        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("🤖 BIM Safety Advisor")
        self.window.geometry(f"{CHATBOT_WIDTH}x{CHATBOT_HEIGHT}")
        self.window.configure(bg=BG_COLOR)

        # Setup UI first (so window appears even if advisor fails)
        self.setup_ui()

        # Initialize advisor (may fail, but UI will still work)
        try:
            self._initialize_advisor()
        except Exception as e:
            logging.exception("Failed to initialize advisor")
            self.show_error_message(f"Advisor initialization failed:\n\n{str(e)}\n\nYou can still use the chatbot, but responses may be limited.")

        # Send welcome message
        self.send_welcome_message()

        logging.info("Chatbot window opened")

    def _initialize_advisor(self):
        """Initialize HazardAdvisor from Phase 4 with robust error handling"""
        try:
            # Add Phase 4 to path
            phase4_dir = Path(__file__).parent.parent / "04_RAG_Based_LLM_Safety_Advisory"
            if not phase4_dir.exists():
                logging.error(f"Phase 4 directory not found: {phase4_dir}")
                self.advisor = None
                return

            if str(phase4_dir) not in sys.path:
                sys.path.insert(0, str(phase4_dir))

            # Set API key in environment
            os.environ["LLM_API_KEY"] = self.api_key

            # Import advisor (with fallback if metrics_tracker missing)
            try:
                from llm_advisor import HazardAdvisor
            except ImportError as e:
                logging.error(f"Failed to import HazardAdvisor: {e}")
                self.advisor = None
                return

            # Create advisor instance
            try:
                self.advisor = HazardAdvisor()
                logging.info("HazardAdvisor instance created")
            except Exception as e:
                logging.error(f"Failed to create HazardAdvisor: {e}")
                self.advisor = None
                return

            # Patch the query method to handle missing metrics_tracker
            self._patch_advisor_for_gui()

            # Load session data
            hazards_file = self.session_dir / "phase1_outputs" / "hazards_detected.json"
            if hazards_file.exists():
                try:
                    self.advisor.load_hazards(str(hazards_file))
                    logging.info(f"Loaded hazards from {hazards_file.name}")
                except Exception as e:
                    logging.warning(f"Could not load hazards: {e}")

            # Load master RAG data into knowledge base
            master_rag = self.session_dir / "master_rag_training_data.json"
            if master_rag.exists():
                try:
                    self._load_rag_data(master_rag)
                    logging.info("Loaded master RAG dataset")
                except Exception as e:
                    logging.warning(f"Could not load RAG data: {e}")

            logging.info("Chatbot advisor initialized successfully")

        except Exception as e:
            logging.exception(f"Failed to initialize advisor")
            self.advisor = None
            # Don't show messagebox during __init__ - it's handled by the caller

    def _patch_advisor_for_gui(self):
        """Patch the advisor's query method to handle missing metrics_tracker"""
        if not self.advisor:
            return

        try:
            # Store original query method
            original_query = self.advisor.query

            def patched_query(user_question: str) -> str:
                """Patched query that doesn't require metrics_tracker"""
                try:
                    # Try to import metrics tracker (may not exist)
                    try:
                        from metrics_tracker import get_tracker
                        return original_query(user_question)
                    except (ImportError, Exception):
                        # Fallback: manually execute query without metrics
                        return self._query_without_metrics(user_question)
                except Exception as e:
                    logging.error(f"Query error: {e}")
                    return f"I apologize, but I encountered an error processing your question:\n\n{str(e)}\n\nPlease try rephrasing your question."

            # Replace query method
            self.advisor.query = patched_query
            logging.info("Successfully patched advisor query method")
        except Exception as e:
            logging.error(f"Failed to patch advisor: {e}")
            # Continue without patching - original method will be used

    def _query_without_metrics(self, user_question: str) -> str:
        """Execute query without metrics tracker"""
        try:
            # Check if advisor has required components
            if not hasattr(self.advisor, 'vector_db') or self.advisor.vector_db is None:
                return "I apologize, but the knowledge base is not available. Please check that the pipeline completed successfully."

            # Retrieve relevant documents
            try:
                relevant_docs = self.advisor.vector_db.search(user_question, top_k=5)
            except Exception as e:
                logging.error(f"Vector search failed: {e}")
                relevant_docs = []

            # Build context
            context_parts = []
            for doc in relevant_docs:
                context_parts.append(f"### {doc.get('type', 'UNKNOWN').upper()}\n{doc.get('content', '')}")
            context = "\n\n".join(context_parts) if context_parts else "No relevant context found."

            # Add hazards summary
            hazards_context = ""
            if hasattr(self.advisor, 'current_hazards') and self.advisor.current_hazards:
                hazard_count = len(self.advisor.current_hazards)
                hazards_context = f"Current hazard analysis contains {hazard_count} detected hazards."

            # Build system prompt
            system_prompt = f"""You are a friendly and knowledgeable construction safety advisor. You're here to help with questions about the current BIM safety analysis.

Be conversational and natural:
- Respond like a helpful colleague, not a formal report
- Answer what's asked - don't volunteer extra information unless requested
- Keep responses concise and to the point
- Use simple language when possible
- If someone just greets you, greet them back naturally

Current project context:
{hazards_context}

Available information:
{context}
"""

            # Build messages
            messages = [{"role": "system", "content": system_prompt}]

            # Add recent conversation history
            if hasattr(self.advisor, 'conversation_history') and self.advisor.conversation_history:
                recent_history = [msg for msg in self.advisor.conversation_history if msg.get('role') in ['user', 'assistant']][-10:]
                messages.extend(recent_history)

            # Add current question
            messages.append({"role": "user", "content": user_question})

            # Generate response
            if hasattr(self.advisor, 'llm_client') and self.advisor.llm_client:
                try:
                    response, _ = self.advisor.llm_client.generate(messages)
                except Exception as e:
                    logging.error(f"LLM generation failed: {e}")
                    response = self._fallback_response(user_question, relevant_docs)
            else:
                response = self._fallback_response(user_question, relevant_docs)

            # Save to conversation history
            if hasattr(self.advisor, 'conversation_history'):
                self.advisor.conversation_history.append({"role": "user", "content": user_question})
                self.advisor.conversation_history.append({"role": "assistant", "content": response})

            return response

        except Exception as e:
            logging.exception("Error in query_without_metrics")
            return f"I encountered an error while processing your question: {str(e)}\n\nPlease try a simpler question or check the logs for details."

    def _fallback_response(self, question: str, docs: list) -> str:
        """Generate fallback response when LLM is unavailable"""
        response = "I don't have access to the LLM service right now, but here's what I found in the knowledge base:\n\n"

        if docs:
            for i, doc in enumerate(docs[:3], 1):
                response += f"{i}. {doc.get('content', 'No content')[:200]}...\n\n"
        else:
            response += "No relevant information found in the knowledge base."

        return response

    def _load_rag_data(self, master_rag_file: Path):
        """Load master RAG data into the advisor's vector database"""
        try:
            with open(master_rag_file) as f:
                rag_data = json.load(f)

            # Convert RAG data to document format
            documents = []

            # Add workflow summaries
            if 'workflow_summary' in rag_data:
                for phase_key, phase_info in rag_data['workflow_summary'].items():
                    doc = {
                        'id': phase_key,
                        'type': 'workflow',
                        'content': f"{phase_info.get('name', '')}: {phase_info.get('purpose', '')}. Output: {phase_info.get('output', '')}"
                    }
                    documents.append(doc)

            # Add knowledge base entries
            if 'knowledge_base' in rag_data:
                kb = rag_data['knowledge_base']
                if 'hazard_types_explained' in kb:
                    for hazard_type, info in kb['hazard_types_explained'].items():
                        doc = {
                            'id': f"hazard_{hazard_type}",
                            'type': 'hazard_type',
                            'content': f"{hazard_type}: {info.get('definition', '')}. Threshold: {info.get('threshold', '')}. Regulation: {info.get('regulation', '')}"
                        }
                        documents.append(doc)

            # Add Q&A examples
            if 'q_and_a_training_examples' in rag_data:
                for i, qa in enumerate(rag_data['q_and_a_training_examples']):
                    doc = {
                        'id': f"qa_{i}",
                        'type': 'qa',
                        'content': f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}"
                    }
                    documents.append(doc)

            # Add documents to vector database
            if documents and hasattr(self.advisor, 'vector_db') and self.advisor.vector_db is not None:
                # Extend existing documents
                existing = getattr(self.advisor.vector_db, 'documents', None) or []
                all_docs = existing + documents
                self.advisor.vector_db.add_documents(all_docs)
                logging.info(f"Loaded {len(documents)} RAG documents into vector database")
        except Exception as e:
            logging.error(f"Error loading RAG data: {e}")
            # Don't crash - continue with limited functionality

    def setup_ui(self):
        """Setup light mode chat interface"""
        # Top info bar
        self.create_info_bar()

        # Chat history
        self.create_chat_area()

        # Quick questions
        self.create_quick_questions()

        # Input area
        self.create_input_area()

        # Bottom toolbar
        self.create_toolbar()

    def create_info_bar(self):
        """Create clean session info bar"""
        # Mint accent bar
        accent_bar = tk.Frame(self.window, bg=HEADER_BG, height=8)
        accent_bar.pack(fill=tk.X)

        # Info bar
        info_bar = tk.Frame(self.window, bg=BG_COLOR, height=45)
        info_bar.pack(fill=tk.X)
        info_bar.pack_propagate(False)

        # Load session stats
        try:
            summary_file = self.session_dir / "phase1_outputs" / "run_summary.json"
            if summary_file.exists():
                with open(summary_file) as f:
                    summary = json.load(f)
                    hazard_count = summary['statistics']['total_hazards']
            else:
                hazard_count = "?"

            report_file = self.session_dir / "phase3_outputs" / "report.json"
            if report_file.exists():
                with open(report_file) as f:
                    report = json.load(f)
                    component_count = report['total_components']
            else:
                component_count = "?"

            info_text = f"Session: {self.session_dir.name.replace('session_', '')}  •  {hazard_count} Hazards  •  {component_count} Guardrails"
        except Exception as e:
            logging.error(f"Error loading session stats: {e}")
            info_text = f"Session: {self.session_dir.name}"

        tk.Label(
            info_bar,
            text=info_text,
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        ).pack(expand=True, pady=SPACE_SM)

    def create_chat_area(self):
        """Create scrollable chat history area"""
        chat_frame = tk.Frame(self.window, bg=BG_COLOR)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=SPACE_MD, pady=(0, SPACE_MD))

        # Create canvas with scrollbar for custom message bubbles
        canvas = tk.Canvas(chat_frame, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=canvas.yview)

        self.chat_container = tk.Frame(canvas, bg=BG_COLOR)

        # Configure canvas scrolling
        self.chat_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.chat_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.chat_canvas = canvas

        # Enable mouse wheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def create_quick_questions(self):
        """Create clean quick question buttons"""
        quick_frame = tk.Frame(self.window, bg=BG_COLOR)
        quick_frame.pack(fill=tk.X, padx=SPACE_MD, pady=(SPACE_SM, SPACE_SM))

        tk.Label(
            quick_frame,
            text="💡  Quick Questions",
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        ).pack(anchor="w", pady=(0, SPACE_XS))

        # Create clean question buttons
        btn_container = tk.Frame(quick_frame, bg=BG_COLOR)
        btn_container.pack(fill="x")

        for question in QUICK_QUESTIONS[:3]:  # Show first 3
            btn = tk.Button(
                btn_container,
                text=f"▶  {question}",
                command=lambda q=question: self.send_message(q),
                bg="#ffffff",
                fg=TEXT_BLACK,
                activebackground="#f5f5f5",
                activeforeground=TEXT_BLACK,
                relief="flat",
                borderwidth=0,
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                anchor="w",
                padx=SPACE_SM,
                pady=SPACE_XS,
                cursor="hand2"
            )
            btn.pack(fill="x", pady=2)

    def create_input_area(self):
        """Create clean message input area"""
        input_container = tk.Frame(self.window, bg=BG_COLOR)
        input_container.pack(fill=tk.X, padx=SPACE_MD, pady=(0, SPACE_SM))

        tk.Label(
            input_container,
            text="✏️  Type your message",
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        ).pack(anchor="w", pady=(0, SPACE_XS))

        # Input frame with text and send button
        entry_frame = tk.Frame(input_container, bg="#ffffff")
        entry_frame.pack(fill=tk.X)

        self.input_text = tk.Text(
            entry_frame,
            height=3,
            width=50,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            bg="#ffffff",
            fg=TEXT_BLACK,
            relief=tk.FLAT,
            borderwidth=0,
            padx=SPACE_SM,
            pady=SPACE_SM,
            insertbackground=TEXT_BLACK
        )
        self.input_text.pack(side="left", fill="both", expand=True, padx=SPACE_XS, pady=SPACE_XS)
        self.input_text.bind("<Return>", self._on_enter_key)
        self.input_text.bind("<Shift-Return>", lambda e: None)

        self.send_btn = tk.Button(
            entry_frame,
            text="SEND ➤",
            command=self._on_send_button,
            bg=PRIMARY_COLOR,
            fg=TEXT_ON_PRIMARY,
            activebackground=PRIMARY_HOVER,
            activeforeground=TEXT_ON_PRIMARY,
            relief="flat",
            borderwidth=0,
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            padx=SPACE_LG,
            pady=SPACE_SM,
            cursor="hand2"
        )
        self.send_btn.pack(side="right", padx=SPACE_SM, pady=SPACE_SM)

    def create_toolbar(self):
        """Create clean bottom toolbar"""
        toolbar = tk.Frame(self.window, bg=BG_SECONDARY)
        toolbar.pack(fill=tk.X, padx=SPACE_MD, pady=(0, SPACE_MD))

        # Clean flat buttons
        buttons = [
            ("📋 Copy", self.copy_conversation, BUTTON_STYLE_SECONDARY),
            ("💾 Save", self.export_conversation, BUTTON_STYLE_SUCCESS),
            ("🗑 Clear", self.clear_conversation, BUTTON_STYLE_DANGER),
        ]

        for text, command, style in buttons:
            btn = tk.Button(
                toolbar,
                text=text,
                command=command,
                **style,
                padx=SPACE_MD,
                pady=SPACE_XS
            )
            btn.pack(side="left", padx=SPACE_XS, pady=SPACE_XS)

    def send_welcome_message(self):
        """Send initial welcome message"""
        try:
            summary_file = self.session_dir / "phase1_outputs" / "run_summary.json"
            if summary_file.exists():
                with open(summary_file) as f:
                    summary = json.load(f)

                categories = summary.get('hazards_by_category', {})
                if categories:
                    category_list = '\n'.join([f"  • {count} {category}" for category, count in categories.items()])
                    welcome = f"""Hello! I'm your BIM Safety Advisor.

I've analyzed your building model and found:
• Total Hazards: {summary['statistics']['total_hazards']}

Categories:
{category_list}

How can I help improve construction safety for this project?"""
                else:
                    welcome = f"Hello! I've found {summary['statistics']['total_hazards']} safety hazards in your building model. How can I assist you?"
            else:
                welcome = "Hello! I'm ready to answer questions about your BIM safety analysis. What would you like to know?"

        except Exception as e:
            logging.error(f"Error loading welcome message: {e}")
            welcome = "Hello! I'm your BIM Safety Advisor. How can I help you today?"

        self.add_message(ASSISTANT_PREFIX, welcome, is_user=False)

    def show_error_message(self, message: str):
        """Display an error message in the chat"""
        self.add_message("System", f"⚠️ {message}", is_user=False)

    def _on_enter_key(self, event):
        """Handle Enter key in input box"""
        # Check if Shift is held
        if event.state & 0x1:  # Shift+Enter = newline
            return
        else:  # Enter alone = send
            self._on_send_button()
            return "break"  # Prevent newline

    def _on_send_button(self):
        """Handle send button click"""
        if self.is_waiting:
            return  # Don't send while waiting for response

        user_input = self.input_text.get("1.0", tk.END).strip()
        if user_input and len(user_input) <= MAX_MESSAGE_LENGTH:
            self.send_message(user_input)
            self.input_text.delete("1.0", tk.END)
        elif len(user_input) > MAX_MESSAGE_LENGTH:
            messagebox.showwarning("Message Too Long", f"Please limit your message to {MAX_MESSAGE_LENGTH} characters.")

    def send_message(self, user_input: str):
        """Send message to chatbot in background thread"""
        if self.is_waiting:
            return

        # Display user message
        self.add_message(USER_PREFIX, user_input, is_user=True)

        # Disable input while processing (grayed out)
        self.is_waiting = True
        self.input_text.config(state=tk.DISABLED, bg="#e0e0e0")
        self.send_btn.config(state=tk.DISABLED, bg="#9e9e9e")

        # Show thinking indicator
        thinking_bubble = self.add_thinking_indicator()

        # Query in background thread
        def query_thread():
            try:
                if self.advisor and hasattr(self.advisor, 'query'):
                    response = self.advisor.query(user_input)
                elif self.advisor:
                    # Advisor exists but query method might not work
                    try:
                        response = self._query_without_metrics(user_input)
                    except Exception as e:
                        logging.error(f"Query fallback failed: {e}")
                        response = "I apologize, but I'm having trouble processing your question. The chatbot may not be fully initialized."
                else:
                    response = "I apologize, but the chatbot advisor is not available. Please check:\n\n1. Phase 4 dependencies are installed\n2. API key is configured correctly\n3. Pipeline completed successfully\n\nCheck gui_application.log for details."

            except Exception as e:
                logging.exception(f"Error querying chatbot")
                response = f"I encountered an error processing your question:\n\n{str(e)}\n\nPlease try again or rephrase your question."

            # Update UI in main thread
            self.window.after(0, lambda: self._handle_response(response, thinking_bubble))

        threading.Thread(target=query_thread, daemon=True).start()

    def _handle_response(self, response: str, thinking_bubble):
        """Handle chatbot response in main thread"""
        # Remove thinking indicator
        if thinking_bubble:
            thinking_bubble.destroy()

        # Display response
        self.add_message(ASSISTANT_PREFIX, response, is_user=False)

        # Store in history
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": self.input_text.get("1.0", tk.END).strip() if not self.is_waiting else "",
            "assistant": response
        })

        # Re-enable input (restore clean styling)
        self.is_waiting = False
        self.input_text.config(state=tk.NORMAL, bg="#ffffff")
        self.send_btn.config(state=tk.NORMAL, bg=PRIMARY_COLOR)

        # Scroll to bottom
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def add_message(self, sender: str, message: str, is_user: bool):
        """Add clean message bubble to chat"""
        # Create message frame
        msg_container = tk.Frame(self.chat_container, bg=BG_COLOR)
        msg_container.pack(fill=tk.X, pady=SPACE_SM)

        # Determine bubble color and alignment (clean pastel style)
        if is_user:
            bubble_bg = CHAT_USER_BG    # Light blue from config
            anchor = "e"
            padx = (80, 0)
        else:
            bubble_bg = CHAT_ASSISTANT_BG  # Light gray from config
            anchor = "w"
            padx = (0, 80)

        # Clean message bubble without heavy borders
        bubble = tk.Frame(msg_container, bg=bubble_bg)
        bubble.pack(anchor=anchor, padx=padx)

        # Simple sender label (black text)
        sender_label = tk.Label(
            bubble,
            text=sender,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            fg=TEXT_BLACK,
            bg=bubble_bg
        )
        sender_label.pack(anchor="w", padx=SPACE_SM, pady=(SPACE_XS, 0))

        # Message text
        msg_text = tk.Text(
            bubble,
            wrap=tk.WORD,
            font=FONT_BODY,
            bg=bubble_bg,
            fg=TEXT_BLACK,
            relief=tk.FLAT,
            borderwidth=0,
            padx=SPACE_MD,
            pady=SPACE_SM,
            height=1,  # Auto-adjust
            state=tk.NORMAL
        )
        msg_text.pack(fill=tk.X, padx=SPACE_XS, pady=(0, SPACE_XS))

        # Insert text and calculate height
        msg_text.insert("1.0", message)
        msg_text.config(state=tk.DISABLED)

        # Auto-resize text widget
        line_count = int(msg_text.index('end-1c').split('.')[0])
        msg_text.config(height=min(line_count, 20))  # Max 20 lines per bubble

        # Scroll to bottom
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def add_thinking_indicator(self):
        """Add clean 'thinking' indicator bubble"""
        thinking_container = tk.Frame(self.chat_container, bg=BG_COLOR)
        thinking_container.pack(fill=tk.X, pady=SPACE_SM)

        # Clean bubble with soft styling
        bubble = tk.Frame(thinking_container, bg=CHAT_ASSISTANT_BG)
        bubble.pack(anchor="w", padx=(0, 100))

        # Simple sender label
        tk.Label(
            bubble,
            text=ASSISTANT_PREFIX,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            fg=TEXT_BLACK,
            bg=CHAT_ASSISTANT_BG
        ).pack(anchor="w", padx=SPACE_SM, pady=(SPACE_XS, 0))

        # Thinking text with soft orange color
        tk.Label(
            bubble,
            text="⏳  Thinking...",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg=CHAT_THINKING_COLOR,
            bg=CHAT_ASSISTANT_BG
        ).pack(anchor="w", padx=SPACE_MD, pady=(0, SPACE_SM))

        # Scroll to bottom
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

        return thinking_container

    def copy_conversation(self):
        """Copy conversation to clipboard"""
        try:
            conversation_text = ""
            for widget in self.chat_container.winfo_children():
                # Extract text from message bubbles
                for child in widget.winfo_children():
                    if isinstance(child, tk.Frame):
                        for subchild in child.winfo_children():
                            if isinstance(subchild, tk.Text):
                                text = subchild.get("1.0", tk.END).strip()
                                conversation_text += text + "\n\n"

            self.window.clipboard_clear()
            self.window.clipboard_append(conversation_text)
            messagebox.showinfo("Copied", "Conversation copied to clipboard!")
        except Exception as e:
            logging.error(f"Error copying conversation: {e}")
            messagebox.showerror("Error", f"Failed to copy conversation:\n{str(e)}")

    def export_conversation(self):
        """Export conversation to file"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filepath:
            try:
                if filepath.endswith('.json'):
                    with open(filepath, 'w') as f:
                        json.dump(self.conversation_history, f, indent=2)
                else:
                    # Export as text
                    with open(filepath, 'w') as f:
                        for entry in self.conversation_history:
                            f.write(f"[{entry['timestamp']}]\n")
                            f.write(f"{USER_PREFIX}: {entry['user']}\n")
                            f.write(f"{ASSISTANT_PREFIX}: {entry['assistant']}\n\n")

                messagebox.showinfo("Exported", f"Conversation saved to:\n{filepath}")
            except Exception as e:
                logging.error(f"Error exporting conversation: {e}")
                messagebox.showerror("Export Error", f"Failed to export conversation:\n{str(e)}")

    def clear_conversation(self):
        """Clear conversation history"""
        if messagebox.askyesno("Clear Conversation", "Are you sure you want to clear the conversation history?"):
            # Clear chat display
            for widget in self.chat_container.winfo_children():
                widget.destroy()

            # Clear history
            self.conversation_history.clear()

            # Send new welcome message
            self.send_welcome_message()

            logging.info("Conversation cleared")
