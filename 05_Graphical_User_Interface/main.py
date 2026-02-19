#!/usr/bin/env python3
"""
BIM Safety Analysis System - Production-Grade Dashboard
Clean Pastel Theme - Simple and Elegant
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import logging
from pathlib import Path
from typing import Optional

# Import local modules
from gui_config import *
from utils import *
from pipeline_controller import PipelineController
from chatbot_interface import ChatbotWindow


class BIMSafetyGUI:
    """Production-grade dashboard for BIM Safety Analysis"""

    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.resizable(True, True)
        self.root.configure(bg=BG_COLOR)

        # Initialize components
        self.controller = PipelineController()
        self.chatbot_window = None

        # State variables
        self.ifc_file = None
        self.api_key = None
        self.current_session = None
        self.is_running = False

        # UI variables
        self.phase_vars = {}
        self.phase_status_labels = {}  # Track phase status UI elements
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Ready")
        self.file_status_var = tk.StringVar(value="No file selected")
        self.api_status_var = tk.StringVar(value="Not configured")

        # Setup logging
        log_file = Path(__file__).parent / LOG_FILE
        setup_logging(log_file)

        # Load API key if exists
        api_key_file = Path(__file__).parent / API_KEY_FILE
        self.api_key = load_api_key(api_key_file)
        if not self.api_key:
            self.api_key = API_KEY

        # Update API status
        if self.api_key:
            self.api_status_var.set("Connected")

        # Setup UI
        self.setup_ui()

        logging.info("=== BIM Safety Analysis System Started ===")

    def setup_ui(self):
        """Setup clean pastel interface"""
        # Configure root grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)  # Accent bar
        self.root.rowconfigure(1, weight=0)  # Title bar
        self.root.rowconfigure(2, weight=1)  # Main content

        # Create main sections
        self.create_header()
        self.create_main_content()

    def create_header(self):
        """Create simple mint green accent bar"""
        # Mint green accent bar at top
        header = tk.Frame(self.root, bg=HEADER_BG, height=8)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        # Title bar below accent
        title_bar = tk.Frame(self.root, bg=BG_COLOR, height=HEADER_HEIGHT-8)
        title_bar.grid(row=1, column=0, sticky="ew")
        title_bar.grid_propagate(False)

        # Configure columns
        title_bar.columnconfigure(0, weight=0)
        title_bar.columnconfigure(1, weight=1)
        title_bar.columnconfigure(2, weight=0)

        # Title with icon - larger
        title_frame = tk.Frame(title_bar, bg=BG_COLOR)
        title_frame.grid(row=0, column=0, sticky="w", padx=SPACE_LG, pady=SPACE_SM)

        title_icon = tk.Label(
            title_frame,
            text="🏗️",
            font=(FONT_FAMILY, ICON_SIZE_XL),
            bg=BG_COLOR
        )
        title_icon.pack(side="left", padx=(0, SPACE_SM))

        title_label = tk.Label(
            title_frame,
            text=WINDOW_TITLE,
            font=(FONT_FAMILY, FONT_SIZE_H1, "bold"),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        )
        title_label.pack(side="left")

        # Center: File status - larger icon
        file_frame = tk.Frame(title_bar, bg=BG_COLOR)
        file_frame.grid(row=0, column=1, sticky="w", padx=SPACE_LG, pady=SPACE_SM)

        tk.Label(
            file_frame,
            text="📄",
            font=(FONT_FAMILY, ICON_SIZE_MD),
            bg=BG_COLOR
        ).pack(side="left", padx=(0, SPACE_XS))

        self.file_status_label = tk.Label(
            file_frame,
            textvariable=self.file_status_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        )
        self.file_status_label.pack(side="left")

        # Right: API status - larger
        api_frame = tk.Frame(title_bar, bg=BG_COLOR)
        api_frame.grid(row=0, column=2, sticky="e", padx=SPACE_LG, pady=SPACE_SM)

        self.api_dot = tk.Label(
            api_frame,
            text="●",
            font=(FONT_FAMILY, ICON_SIZE_MD),
            fg=SUCCESS_COLOR,
            bg=BG_COLOR
        )
        self.api_dot.pack(side="left", padx=(0, SPACE_XS))

        api_text = tk.Label(
            api_frame,
            text="API:",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        )
        api_text.pack(side="left", padx=(0, SPACE_XS))

        self.api_label = tk.Label(
            api_frame,
            textvariable=self.api_status_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg=TEXT_BLACK,
            bg=BG_COLOR
        )
        self.api_label.pack(side="left")

        self.update_api_indicator()

    def create_main_content(self):
        """Create main workspace with three colored columns"""
        workspace = tk.Frame(self.root, bg=BG_COLOR)
        workspace.grid(row=2, column=0, sticky="nsew", padx=SPACE_MD, pady=SPACE_MD)

        # Configure grid: Left (25%), Center (50%), Right (25%)
        workspace.columnconfigure(0, weight=1, minsize=320)
        workspace.columnconfigure(1, weight=2, minsize=500)
        workspace.columnconfigure(2, weight=1, minsize=320)
        workspace.rowconfigure(0, weight=1)

        # Create three colored panels
        self.create_control_panel(workspace)
        self.create_status_panel(workspace)
        self.create_results_panel(workspace)

    def create_control_panel(self, parent):
        """Left panel: File selection and phase configuration"""
        panel = self.create_card(parent, "CONFIGURATION", row=0, column=0, padx=(0, SPACE_MD))

        # File selection section - BLACK heading, larger icon
        file_section = tk.Frame(panel, bg=COLUMN_LEFT)
        file_section.pack(fill="x", pady=(0, SPACE_MD))

        tk.Label(
            file_section,
            text="📂  IFC Building Model",
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_LEFT
        ).pack(anchor="w", pady=(0, SPACE_SM))

        browse_btn = tk.Button(
            file_section,
            text="📁  Browse Files",
            command=self.browse_ifc_file,
            bg="#ffffff",
            fg=TEXT_BLACK,
            activebackground="#f5f5f5",
            activeforeground=TEXT_BLACK,
            relief="flat",
            borderwidth=0,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            padx=SPACE_LG,
            pady=SPACE_SM,
            cursor="hand2"
        )
        browse_btn.pack(fill="x", pady=(0, SPACE_SM))

        self.file_display = tk.Label(
            file_section,
            text="No file selected",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg=TEXT_BLACK,
            bg=COLUMN_LEFT,
            anchor="w"
        )
        self.file_display.pack(fill="x")

        # Phase configuration
        # Pipeline Phases - BLACK heading, larger icon
        tk.Label(
            panel,
            text="⚙️  Pipeline Phases",
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_LEFT
        ).pack(anchor="w", pady=(SPACE_MD, SPACE_SM))

        # Create phase toggles
        for phase_num in range(1, 5):
            self.create_phase_toggle(panel, phase_num)

        # Spacer to push buttons to bottom
        tk.Frame(panel, bg=COLUMN_LEFT).pack(fill="both", expand=True)

        # Action buttons at bottom
        action_frame = tk.Frame(panel, bg=COLUMN_LEFT)
        action_frame.pack(fill="x", side="bottom", pady=(SPACE_LG, 0))

        self.start_btn = tk.Button(
            action_frame,
            text="▶  START PIPELINE",
            command=self.start_pipeline,
            bg=PRIMARY_COLOR,
            fg=TEXT_ON_PRIMARY,
            activebackground=PRIMARY_HOVER,
            activeforeground=TEXT_ON_PRIMARY,
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=SPACE_LG,
            pady=SPACE_MD
        )
        self.start_btn.pack(fill="x", pady=(0, SPACE_SM))

        self.stop_btn = tk.Button(
            action_frame,
            text="⬛  STOP",
            command=self.stop_pipeline,
            bg=ERROR_COLOR,
            fg=TEXT_ON_PRIMARY,
            activebackground="#ef5350",
            activeforeground=TEXT_ON_PRIMARY,
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=SPACE_LG,
            pady=SPACE_SM,
            state=tk.DISABLED
        )
        self.stop_btn.pack(fill="x")

    def create_phase_toggle(self, parent, phase_num):
        """Create phase toggle with pure BLACK text, larger icons, and aligned layout using grid"""
        row_frame = tk.Frame(parent, bg=COLUMN_LEFT)
        row_frame.pack(fill="x", pady=3)

        # Use grid for precise alignment
        row_frame.columnconfigure(0, minsize=30)   # Checkbox column
        row_frame.columnconfigure(1, minsize=40)   # Icon column - fixed width
        row_frame.columnconfigure(2, weight=1)     # Info column - expandable

        # Checkbox
        var = tk.BooleanVar(value=True)
        self.phase_vars[phase_num] = var

        cb = tk.Checkbutton(
            row_frame,
            variable=var,
            bg=COLUMN_LEFT,
            activebackground=COLUMN_LEFT,
            selectcolor=COLUMN_LEFT,
            fg=TEXT_BLACK,
            activeforeground=TEXT_BLACK,
            relief=tk.FLAT
        )
        cb.grid(row=0, column=0, rowspan=2, sticky="w")

        # Icon - use Segoe UI Emoji font for proper emoji rendering on Windows
        icon = tk.Label(
            row_frame,
            text=PHASE_ICONS[phase_num],
            font=("Segoe UI Emoji", ICON_SIZE_LG),
            bg=COLUMN_LEFT
        )
        icon.grid(row=0, column=1, rowspan=2, sticky="w")

        # Name
        name_label = tk.Label(
            row_frame,
            text=PHASE_NAMES[phase_num],
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_LEFT,
            anchor="w"
        )
        name_label.grid(row=0, column=2, sticky="w")

        # Description
        desc_label = tk.Label(
            row_frame,
            text=PHASE_DESCRIPTIONS[phase_num],
            font=(FONT_FAMILY, FONT_SIZE_PHASE_DESC),
            fg=TEXT_BLACK,
            bg=COLUMN_LEFT,
            anchor="w"
        )
        desc_label.grid(row=1, column=2, sticky="w")

    def create_status_panel(self, parent):
        """Center panel: Pipeline status and logs"""
        panel = self.create_card(parent, "PIPELINE STATUS", row=0, column=1, padx=SPACE_SM)

        # Status indicator row - black text
        status_row = tk.Frame(panel, bg=COLUMN_CENTER)
        status_row.pack(fill="x", pady=(0, SPACE_MD))

        self.status_dot = tk.Label(
            status_row,
            text="●",
            font=(FONT_FAMILY, ICON_SIZE_LG),
            fg=STATUS_IDLE,
            bg=COLUMN_CENTER
        )
        self.status_dot.pack(side="left", padx=(0, SPACE_SM))

        self.status_text = tk.Label(
            status_row,
            textvariable=self.status_var,
            font=(FONT_FAMILY, FONT_SIZE_H2, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_CENTER
        )
        self.status_text.pack(side="left")

        # Progress bar
        progress_container = tk.Frame(panel, bg=COLUMN_CENTER)
        progress_container.pack(fill="x", pady=(0, SPACE_LG))

        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "Custom.Horizontal.TProgressbar",
            troughcolor="#ffffff",
            background=SUCCESS_COLOR,
            borderwidth=0,
            thickness=6
        )

        self.progress_bar = ttk.Progressbar(
            progress_container,
            variable=self.progress_var,
            maximum=100,
            style="Custom.Horizontal.TProgressbar",
            mode='determinate'
        )
        self.progress_bar.pack(fill="x")

        # Phase status cards container
        self.phase_cards_frame = tk.Frame(panel, bg=COLUMN_CENTER)
        self.phase_cards_frame.pack(fill="both", expand=True, pady=(0, SPACE_MD))

        # Create placeholder phase status cards
        self.create_phase_status_cards()

        # Log output section - BLACK heading
        tk.Label(
            panel,
            text="📋  Output Log",
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_CENTER
        ).pack(anchor="w", pady=(0, SPACE_XS))

        self.log_text = tk.Text(
            panel,
            height=LOG_LINES_VISIBLE,
            wrap=tk.WORD,
            font=FONT_MONO,
            bg="#ffffff",
            fg=TEXT_BLACK,
            relief=tk.FLAT,
            borderwidth=0,
            padx=SPACE_SM,
            pady=SPACE_SM,
            state=tk.DISABLED
        )
        self.log_text.pack(fill="x")

    def create_phase_status_cards(self):
        """Create phase status cards with BLACK text and aligned icons using grid"""
        for widget in self.phase_cards_frame.winfo_children():
            widget.destroy()

        self.phase_status_labels = {}

        for phase_num in range(1, 4):  # Only show phases 1-3
            card = tk.Frame(self.phase_cards_frame, bg="#ffffff")
            card.pack(fill="x", pady=2)

            # Use grid for precise alignment
            card.columnconfigure(0, minsize=40)  # Icon column - fixed width
            card.columnconfigure(1, weight=1)     # Name column - expandable
            card.columnconfigure(2, minsize=80)   # Status column - fixed width

            # Icon - use Segoe UI Emoji font for proper emoji rendering on Windows
            icon = tk.Label(
                card,
                text=PHASE_ICONS[phase_num],
                font=("Segoe UI Emoji", ICON_SIZE_MD),
                bg="#ffffff"
            )
            icon.grid(row=0, column=0, padx=(SPACE_SM, 0), pady=SPACE_XS, sticky="w")

            # Name
            name = tk.Label(
                card,
                text=PHASE_NAMES[phase_num],
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                bg="#ffffff",
                fg=TEXT_BLACK
            )
            name.grid(row=0, column=1, pady=SPACE_XS, sticky="w")

            # Status
            status_label = tk.Label(
                card,
                text="Pending",
                font=(FONT_FAMILY, FONT_SIZE_SMALL),
                bg="#ffffff",
                fg="#757575"
            )
            status_label.grid(row=0, column=2, padx=(0, SPACE_SM), pady=SPACE_XS, sticky="e")

            self.phase_status_labels[phase_num] = status_label

    def create_results_panel(self, parent):
        """Right panel: Results and actions"""
        panel = self.create_card(parent, "RESULTS & ACTIONS", row=0, column=2, padx=(SPACE_SM, 0))

        # Summary stats with ORANGE and GREEN colors + underlines
        self.stats_frame = tk.Frame(panel, bg=COLUMN_RIGHT)
        self.stats_frame.pack(fill="x", pady=(0, SPACE_MD))

        # Hazards stat - ORANGE
        self.hazards_label = tk.Label(
            self.stats_frame,
            text="—",
            font=(FONT_FAMILY, 40, "bold"),
            fg=STAT_ORANGE,
            bg=COLUMN_RIGHT
        )
        self.hazards_label.pack()

        tk.Label(
            self.stats_frame,
            text="Hazards Detected",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_RIGHT
        ).pack()

        # Orange underline
        tk.Frame(self.stats_frame, height=3, bg=STAT_ORANGE, width=120).pack(pady=(SPACE_XS, 0))

        tk.Frame(self.stats_frame, height=SPACE_LG, bg=COLUMN_RIGHT).pack()

        # Guardrails stat - GREEN
        self.guardrails_label = tk.Label(
            self.stats_frame,
            text="—",
            font=(FONT_FAMILY, 40, "bold"),
            fg=STAT_GREEN,
            bg=COLUMN_RIGHT
        )
        self.guardrails_label.pack()

        tk.Label(
            self.stats_frame,
            text="Guardrails Generated",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_RIGHT
        ).pack()

        # Green underline
        tk.Frame(self.stats_frame, height=3, bg=STAT_GREEN, width=150).pack(pady=(SPACE_XS, 0))

        # Action buttons
        # Quick Actions - BLACK heading, larger icon
        tk.Label(
            panel,
            text="🚀  Quick Actions",
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=COLUMN_RIGHT
        ).pack(anchor="w", pady=(SPACE_MD, SPACE_SM))

        # Store button references
        self.result_buttons = {}

        actions = [
            ("View Summary", "📊", self.view_results),
            ("Open Chatbot", "💬", self.open_chatbot),
            ("Output Folder", "📁", self.open_folder),
            ("Phase 2 IFC", "🎨", self.highlight_phase2_file),
            ("Phase 3 IFC", "🛡", self.highlight_phase3_file),  # Use simple shield without variation selector
        ]

        for label, icon, command in actions:
            # Create button frame with grid for aligned icon and text
            btn_frame = tk.Frame(panel, bg="#ffffff")
            btn_frame.pack(fill="x", pady=2)
            btn_frame.columnconfigure(0, minsize=36)  # Fixed width for icon
            btn_frame.columnconfigure(1, weight=1)    # Expandable for text

            # Icon label - always black
            icon_lbl = tk.Label(
                btn_frame,
                text=icon,
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                bg="#ffffff",
                fg=TEXT_BLACK
            )
            icon_lbl.grid(row=0, column=0, padx=(SPACE_SM, 0), pady=SPACE_SM, sticky="w")

            # Text button (clickable) - black even when disabled
            btn = tk.Button(
                btn_frame,
                text=label,
                command=command,
                bg="#ffffff",
                fg=TEXT_BLACK,
                disabledforeground=TEXT_BLACK,  # Keep text black when disabled
                activebackground="#f5f5f5",
                activeforeground=TEXT_BLACK,
                relief="flat",
                borderwidth=0,
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                anchor="w",
                pady=SPACE_SM,
                state=tk.DISABLED,
                cursor="hand2"
            )
            btn.grid(row=0, column=1, sticky="ew")

            # Make the whole frame clickable
            btn_frame.bind("<Button-1>", lambda e, cmd=command, b=btn: cmd() if str(b['state']) == 'normal' else None)
            icon_lbl.bind("<Button-1>", lambda e, cmd=command, b=btn: cmd() if str(b['state']) == 'normal' else None)

            self.result_buttons[label] = btn

    def create_card(self, parent, title, row, column, **grid_kwargs):
        """Create simple solid colored panel with black heading"""
        # Define column colors
        column_colors = {
            "CONFIGURATION": COLUMN_LEFT,      # Soft sky blue
            "PIPELINE STATUS": COLUMN_CENTER,  # Soft gray
            "RESULTS & ACTIONS": COLUMN_RIGHT, # Soft periwinkle
        }

        panel_color = column_colors.get(title, COLUMN_CENTER)

        # Simple solid colored panel
        card = tk.Frame(parent, bg=panel_color)
        card.grid(row=row, column=column, sticky="nsew", **grid_kwargs)

        # Title at top - PURE BLACK, larger font
        title_label = tk.Label(
            card,
            text=title,
            font=(FONT_FAMILY, FONT_SIZE_H3, "bold"),
            fg=TEXT_BLACK,
            bg=panel_color
        )
        title_label.pack(anchor="w", padx=SPACE_MD, pady=(SPACE_MD, SPACE_SM))

        # Content frame (same color as panel)
        content = tk.Frame(card, bg=panel_color)
        content.pack(fill="both", expand=True, padx=SPACE_MD, pady=(0, SPACE_MD))

        return content

    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================

    def browse_ifc_file(self):
        """Open file browser for IFC file selection"""
        initial_dir = Path(DEFAULT_IFC_DIR) if Path(DEFAULT_IFC_DIR).exists() else Path.home()

        filepath = filedialog.askopenfilename(
            title="Select IFC Building Model",
            initialdir=initial_dir,
            filetypes=[("IFC files", "*.ifc"), ("All files", "*.*")]
        )

        if filepath:
            filepath = Path(filepath)
            is_valid, message = validate_ifc_file(filepath)

            if is_valid:
                self.ifc_file = filepath
                filename = filepath.name
                if len(filename) > 35:
                    filename = filename[:32] + "..."
                self.file_display.config(text=f"✓ {filename}", fg=STAT_GREEN)  # Green success
                self.file_status_var.set(filepath.name)
                self.log_message(f"✓ Selected: {filepath.name}")
            else:
                messagebox.showerror("Invalid File", message)
                self.file_display.config(text="❌ Invalid file", fg="#d32f2f")  # Red error

    def start_pipeline(self):
        """Start pipeline execution"""
        # Validation
        if not self.ifc_file:
            messagebox.showerror("No File Selected", "Please select an IFC file first.")
            return

        if not any(var.get() for var in self.phase_vars.values()):
            messagebox.showerror("No Phases Selected", "Please enable at least one phase.")
            return

        # Check API key if Phase 4 is enabled
        if self.phase_vars[4].get():
            if not self.api_key:
                messagebox.showerror("API Key Required", "Phase 4 (LLM Advisory) requires a valid API key.\n\nPlease configure your OpenRouter API key first.")
                return

        # Confirmation
        phases_to_run = [PHASE_NAMES[i] for i, var in self.phase_vars.items() if var.get()]
        msg = "Start pipeline with following phases?\n\n" + "\n".join(f"  • {p}" for p in phases_to_run)
        msg += f"\n\nFile: {self.ifc_file.name}"

        if not messagebox.askyesno("Confirm Start", msg):
            return

        # Update UI state
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True
        self.status_var.set("Initializing...")
        self.update_status_indicator(STATUS_RUNNING)

        # Reset phase status cards
        for phase_num, label in self.phase_status_labels.items():
            label.config(text="Pending", fg=TEXT_TERTIARY)

        # Clear log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

        # Reset progress
        self.progress_var.set(0)

        # Disable result buttons
        for btn in self.result_buttons.values():
            btn.config(state=tk.DISABLED)

        # Run in thread
        threading.Thread(target=self._run_pipeline_thread, daemon=True).start()

    def stop_pipeline(self):
        """Stop pipeline execution"""
        if messagebox.askyesno("Stop Pipeline", "Are you sure you want to stop the pipeline?\n\nThis may leave the session in an incomplete state."):
            self.is_running = False
            self.log_message("⚠️  Pipeline stopped by user")

    def _run_pipeline_thread(self):
        """Background thread for pipeline execution"""
        try:
            # Create session
            self.log_message("📁 Creating session directory...")
            session_dir = self.controller.create_session(self.ifc_file)
            self.current_session = session_dir
            self.log_message(f"✓ Session: {session_dir.name}")

            # Get enabled phases
            phases_to_run = [i for i, var in self.phase_vars.items() if var.get() and i <= 3]

            # Run each phase
            for phase_num in phases_to_run:
                if not self.is_running:
                    break

                phase_name = PHASE_NAMES[phase_num]
                self.update_status(f"Running Phase {phase_num}...")
                self.update_phase_status(phase_num, "Running", PHASE_COLORS[phase_num])

                # Execute phase
                if phase_num == 1:
                    result = self.controller.run_phase1(
                        callback=lambda p, msg: self.update_progress(phase_num, p, msg)
                    )
                elif phase_num == 2:
                    result = self.controller.run_phase2(
                        callback=lambda p, msg: self.update_progress(phase_num, p, msg)
                    )
                elif phase_num == 3:
                    result = self.controller.run_phase3(
                        callback=lambda p, msg: self.update_progress(phase_num, p, msg)
                    )

                # Check result
                if not result.get("success"):
                    errors = "\n".join(result.get("errors", ["Unknown error"]))
                    self.log_message(f"❌ Phase {phase_num} failed:")
                    self.log_message(errors)
                    self.update_status(f"Failed at Phase {phase_num}")
                    self.update_status_indicator(STATUS_ERROR)
                    self.update_phase_status(phase_num, "Failed", ERROR_COLOR)
                    return

                self.log_message(f"✓ Phase {phase_num} completed")
                self.update_phase_status(phase_num, "Complete", SUCCESS_COLOR)

            # Create master RAG dataset
            phases_enabled = [self.phase_vars[i].get() for i in [1, 2, 3]]
            self.log_message(f"Phases 1-3 enabled: {phases_enabled}")

            if self.is_running and all(phases_enabled):
                self.log_message("📚 Creating master RAG dataset...")
                try:
                    master_rag = self.controller.create_master_rag(
                        callback=lambda p, msg: self.update_status(msg)
                    )

                    if master_rag and master_rag.exists():
                        self.log_message(f"✓ Master RAG created: {master_rag.name}")
                        self.log_message(f"  Location: {master_rag}")
                    else:
                        self.log_message(f"⚠️  Master RAG creation returned None or file not found")
                        self.log_message(f"  Check log for missing llm_training_data.json files")
                except Exception as e:
                    self.log_message(f"❌ Master RAG creation failed: {str(e)}")
                    logging.exception("Master RAG creation error")
            else:
                if not all(phases_enabled):
                    self.log_message(f"⚠️  Master RAG skipped - not all phases 1-3 were enabled")

            # Pipeline complete
            if self.is_running:
                self.root.after(0, lambda: self.progress_var.set(100))
                self.update_status("Pipeline Complete ✓")
                self.update_status_indicator(STATUS_COMPLETE)

                self.log_message("="*50)
                self.log_message("✓ PIPELINE COMPLETE")
                self.log_message("="*50)

                # Get summary
                summary = self.controller.get_session_summary()
                hazard_count = summary.get('hazard_count', 0)
                component_count = summary.get('component_count', 0)

                self.log_message(f"Hazards detected: {hazard_count}")
                self.log_message(f"Guardrails generated: {component_count}")

                # Update stats display
                self.root.after(0, lambda: self.hazards_label.config(text=str(hazard_count)))
                self.root.after(0, lambda: self.guardrails_label.config(text=str(component_count)))

                # Enable result buttons
                self.root.after(0, self._enable_result_buttons)

        except Exception as e:
            logging.exception("Pipeline error")
            self.log_message(f"❌ ERROR: {str(e)}")
            self.update_status("Error")
            self.update_status_indicator(STATUS_ERROR)
            messagebox.showerror("Pipeline Error", f"An error occurred:\n\n{str(e)}\n\nCheck logs for details.")

        finally:
            # Re-enable controls
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.is_running = False

    def _enable_result_buttons(self):
        """Enable result buttons after completion"""
        for btn_name, btn in self.result_buttons.items():
            btn.config(state=tk.NORMAL)

        # Disable chatbot if no API key
        if not self.api_key:
            self.result_buttons["Open Chatbot"].config(state=tk.DISABLED)

    def update_progress(self, phase_num: int, phase_progress: float, message: str):
        """Update progress bar and status message"""
        overall_progress = calculate_progress(phase_num, phase_progress)
        self.root.after(0, lambda: self.progress_var.set(overall_progress * 100))
        self.root.after(0, lambda: self.status_var.set(f"Phase {phase_num}: {message}"))

    def update_status(self, message: str):
        """Update status text"""
        self.root.after(0, lambda: self.status_var.set(message))

    def update_status_indicator(self, color: str):
        """Update main status dot color"""
        self.root.after(0, lambda: self.status_dot.config(fg=color))

    def update_phase_status(self, phase_num: int, status: str, color: str):
        """Update individual phase status with colored badge"""
        if phase_num in self.phase_status_labels:
            # Map status to badge colors (90s style badges!)
            badge_colors = {
                "Pending": "#90a4ae",   # Gray
                "Running": "#29b6f6",   # Cyan/blue (animated feel)
                "Complete": "#66bb6a",  # Green
                "Failed": "#ef5350",    # Red
            }
            badge_bg = badge_colors.get(status, color)
            self.root.after(0, lambda: self.phase_status_labels[phase_num].config(
                text=f" {status} ",
                bg=badge_bg,
                fg=TEXT_ON_PRIMARY
            ))

    def update_api_indicator(self):
        """Update API status indicator"""
        status = self.api_status_var.get()
        color = SUCCESS_COLOR if status == "Connected" else STATUS_IDLE
        self.api_dot.config(fg=color)

    def log_message(self, message: str):
        """Add message to log display"""
        def _log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)

            # Keep only recent lines
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > 100:
                self.log_text.delete("1.0", f"{line_count - 50}.0")

            self.log_text.config(state=tk.DISABLED)

        self.root.after(0, _log)
        logging.info(message)

    # ========================================================================
    # RESULT ACTIONS
    # ========================================================================

    def view_results(self):
        """View results summary"""
        if not self.current_session:
            messagebox.showerror("No Results", "Please run the pipeline first.")
            return

        summary = self.controller.get_session_summary()
        msg = "Pipeline Results\n" + "="*50 + "\n\n"
        msg += f"Session: {Path(summary['session_dir']).name}\n"
        msg += f"IFC File: {summary.get('ifc_file', 'N/A')}\n\n"

        msg += "Phases Completed:\n"
        for phase in summary.get('phases_completed', []):
            msg += f"  ✓ {phase}\n"

        msg += f"\nHazards Detected: {summary.get('hazard_count', 0)}\n"
        msg += f"Guardrails Generated: {summary.get('component_count', 0)}\n"

        messagebox.showinfo("Results Summary", msg)

    def open_chatbot(self):
        """Open chatbot window"""
        if not self.api_key:
            messagebox.showerror("API Key Required", "Please configure your API key first.\n\nEdit api_key.txt or set the LLM_API_KEY environment variable.")
            return

        if not self.current_session:
            messagebox.showerror("No Session", "Please run the pipeline first.")
            return

        # Check if master RAG exists (warn but continue)
        master_rag = self.current_session / "master_rag_training_data.json"
        if not master_rag.exists():
            logging.warning(f"Master RAG not found at: {master_rag}")
            # Check session directory contents
            if self.current_session.exists():
                files = list(self.current_session.iterdir())
                logging.info(f"Session directory contains {len(files)} items:")
                for f in files[:10]:  # Log first 10 files
                    logging.info(f"  - {f.name}")

            result = messagebox.askyesnocancel(
                "Master RAG Not Found",
                f"The master RAG dataset was not found in:\n{master_rag}\n\n"
                "The chatbot will work but may have limited knowledge.\n\n"
                "Do you want to continue anyway?\n\n"
                "(Check gui_application.log for details)"
            )
            if result is None or result is False:
                return  # User clicked Cancel or No

        # Close existing chatbot
        if self.chatbot_window and hasattr(self.chatbot_window, 'window'):
            try:
                self.chatbot_window.window.destroy()
            except:
                pass

        # Open new chatbot
        try:
            self.chatbot_window = ChatbotWindow(self.root, self.current_session, self.api_key)
            logging.info("Chatbot window opened successfully")
        except Exception as e:
            logging.exception("Failed to open chatbot")
            messagebox.showerror("Chatbot Error", f"Failed to open chatbot:\n\n{str(e)}\n\nCheck gui_application.log for details.")

    def open_folder(self):
        """Open output folder"""
        if not self.current_session:
            messagebox.showerror("No Session", "Please run the pipeline first.")
            return

        open_folder_in_explorer(self.current_session)

    def highlight_phase2_file(self):
        """Highlight Phase 2 colored IFC"""
        if not self.current_session:
            messagebox.showerror("No Session", "Please run the pipeline first.")
            return

        phase2_dir = self.current_session / "phase2_outputs"
        if not phase2_dir.exists():
            messagebox.showerror("Not Found", "Phase 2 outputs not found. Did you run Phase 2?")
            return

        colored_files = list(phase2_dir.glob("*_colored.ifc"))
        if not colored_files:
            messagebox.showerror("Not Found", "Colored IFC file not found in Phase 2 outputs.")
            return

        open_file_in_explorer(colored_files[0])

    def highlight_phase3_file(self):
        """Highlight Phase 3 guardrail IFC"""
        if not self.current_session:
            messagebox.showerror("No Session", "Please run the pipeline first.")
            return

        phase3_dir = self.current_session / "phase3_outputs"
        if not phase3_dir.exists():
            messagebox.showerror("Not Found", "Phase 3 outputs not found. Did you run Phase 3?")
            return

        guardrail_files = list(phase3_dir.glob("*_UNIFIED_GUARDRAILS.ifc"))
        if not guardrail_files:
            messagebox.showerror("Not Found", "Guardrail IFC file not found in Phase 3 outputs.")
            return

        open_file_in_explorer(guardrail_files[0])


def main():
    """Main entry point"""
    root = tk.Tk()
    app = BIMSafetyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
