#!/usr/bin/env python3
"""
GUI Widget for Batch Processing

Provides a user-friendly interface for starting and monitoring
large-scale batch processing operations.
"""

import asyncio
import threading
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Any

from ..core.batch_processor import BatchJobStatus, IntelligentBatchProcessor


class BatchProcessingWidget(ttk.Frame):
    """
    GUI widget for batch processing operations.

    Allows users to:
    - Specify episode URLs or load from file
    - Start batch processing with progress monitoring
    - Resume interrupted processes
    - View results and statistics
    """

    def __init__(
        self,
        parent,
        hardware_specs: dict[str, Any],
        download_func: Callable[[str], str],
        mining_func: Callable[[str], dict[str, Any]],
        evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
    ):
        super().__init__(parent)

        self.hardware_specs = hardware_specs
        self.download_func = download_func
        self.mining_func = mining_func
        self.evaluation_func = evaluation_func

        # Processing state
        self.current_batch_id: str | None = None
        self.is_processing = False
        self.processor: IntelligentBatchProcessor | None = None

        # GUI setup
        self._setup_ui()
        self._update_hardware_info()

    def _setup_ui(self):
        """Setup the user interface"""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(
            main_frame, text="Batch Processing", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Hardware info section
        self._create_hardware_info_section(main_frame)

        # Batch configuration section
        self._create_batch_config_section(main_frame)

        # URL input section
        self._create_url_input_section(main_frame)

        # Control buttons
        self._create_control_buttons(main_frame)

        # Progress section
        self._create_progress_section(main_frame)

        # Results section
        self._create_results_section(main_frame)

    def _create_hardware_info_section(self, parent):
        """Create hardware information display"""
        hardware_frame = ttk.LabelFrame(
            parent, text="Hardware Optimization", padding=10
        )
        hardware_frame.pack(fill=tk.X, pady=(0, 10))

        self.hardware_info_text = tk.Text(hardware_frame, height=4, wrap=tk.WORD)
        self.hardware_info_text.pack(fill=tk.X)

        # Scrollbar for hardware info
        hw_scrollbar = ttk.Scrollbar(
            hardware_frame, orient=tk.VERTICAL, command=self.hardware_info_text.yview
        )
        hw_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hardware_info_text.config(yscrollcommand=hw_scrollbar.set)

    def _create_batch_config_section(self, parent):
        """Create batch configuration section"""
        config_frame = ttk.LabelFrame(parent, text="Batch Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))

        # Batch name
        ttk.Label(config_frame, text="Batch Name:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        self.batch_name_var = tk.StringVar(value="Episode Batch Processing")
        batch_name_entry = ttk.Entry(
            config_frame, textvariable=self.batch_name_var, width=40
        )
        batch_name_entry.grid(row=0, column=1, sticky=tk.W + tk.E, padx=(10, 0), pady=2)

        # Parallel processing settings
        ttk.Label(config_frame, text="Max Parallel Downloads:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        self.max_downloads_var = tk.IntVar(value=4)
        downloads_spinbox = ttk.Spinbox(
            config_frame, from_=1, to=8, textvariable=self.max_downloads_var, width=10
        )
        downloads_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        ttk.Label(config_frame, text="Max Parallel Mining:").grid(
            row=2, column=0, sticky=tk.W, pady=2
        )
        self.max_mining_var = tk.IntVar(value=8)
        mining_spinbox = ttk.Spinbox(
            config_frame, from_=1, to=16, textvariable=self.max_mining_var, width=10
        )
        mining_spinbox.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        ttk.Label(config_frame, text="Max Parallel Evaluation:").grid(
            row=3, column=0, sticky=tk.W, pady=2
        )
        self.max_evaluation_var = tk.IntVar(value=6)
        eval_spinbox = ttk.Spinbox(
            config_frame, from_=1, to=12, textvariable=self.max_evaluation_var, width=10
        )
        eval_spinbox.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        # Resume option
        self.resume_enabled_var = tk.BooleanVar(value=True)
        resume_checkbox = ttk.Checkbutton(
            config_frame,
            text="Enable resume from interruptions",
            variable=self.resume_enabled_var,
        )
        resume_checkbox.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))

        # Configure column weights
        config_frame.columnconfigure(1, weight=1)

    def _create_url_input_section(self, parent):
        """Create URL input section"""
        url_frame = ttk.LabelFrame(parent, text="Episode URLs", padding=10)
        url_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # URL input methods
        input_method_frame = ttk.Frame(url_frame)
        input_method_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            input_method_frame, text="Load from File", command=self._load_urls_from_file
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(
            input_method_frame, text="Paste URLs", command=self._show_url_paste_dialog
        ).pack(side=tk.LEFT)

        # URL list
        url_list_frame = ttk.Frame(url_frame)
        url_list_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview for URLs
        columns = ("index", "url", "status")
        self.url_tree = ttk.Treeview(
            url_list_frame, columns=columns, show="headings", height=8
        )

        # Configure columns
        self.url_tree.heading("index", text="#")
        self.url_tree.heading("url", text="Episode URL")
        self.url_tree.heading("status", text="Status")

        self.url_tree.column("index", width=50, anchor=tk.CENTER)
        self.url_tree.column("url", width=400)
        self.url_tree.column("status", width=100, anchor=tk.CENTER)

        self.url_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar for URL list
        url_scrollbar = ttk.Scrollbar(
            url_list_frame, orient=tk.VERTICAL, command=self.url_tree.yview
        )
        url_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.url_tree.config(yscrollcommand=url_scrollbar.set)

        # URL count
        self.url_count_label = ttk.Label(url_frame, text="0 episodes")
        self.url_count_label.pack(pady=(10, 0))

    def _create_control_buttons(self, parent):
        """Create control buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_button = ttk.Button(
            button_frame,
            text="Start Batch Processing",
            command=self._start_batch_processing,
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Processing",
            command=self._stop_batch_processing,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))

        self.resume_button = ttk.Button(
            button_frame, text="Resume Interrupted", command=self._show_resume_dialog
        )
        self.resume_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame, text="View All Batches", command=self._show_batch_history
        ).pack(side=tk.RIGHT)

    def _create_progress_section(self, parent):
        """Create progress monitoring section"""
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        # Overall progress
        ttk.Label(progress_frame, text="Overall Progress:").pack(anchor=tk.W)
        self.overall_progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.overall_progress.pack(fill=tk.X, pady=(5, 10))

        # Current phase
        self.current_phase_label = ttk.Label(progress_frame, text="Ready to start")
        self.current_phase_label.pack(anchor=tk.W)

        # Detailed progress
        self.detailed_progress_label = ttk.Label(progress_frame, text="")
        self.detailed_progress_label.pack(anchor=tk.W)

        # Resource usage
        resource_frame = ttk.Frame(progress_frame)
        resource_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(resource_frame, text="Resource Usage:").pack(anchor=tk.W)
        self.resource_usage_label = ttk.Label(resource_frame, text="")
        self.resource_usage_label.pack(anchor=tk.W)

    def _create_results_section(self, parent):
        """Create results display section"""
        results_frame = ttk.LabelFrame(parent, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True)

        # Results text area
        self.results_text = tk.Text(results_frame, height=6, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Scrollbar for results
        results_scrollbar = ttk.Scrollbar(
            results_frame, orient=tk.VERTICAL, command=self.results_text.yview
        )
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_text.config(yscrollcommand=results_scrollbar.set)

    def _update_hardware_info(self):
        """Update hardware information display"""
        memory_gb = self.hardware_specs.get("memory_gb", 16)
        cpu_cores = self.hardware_specs.get("cpu_cores", 8)
        chip_type = self.hardware_specs.get("chip_type", "Unknown")

        # Determine optimization level
        if memory_gb >= 64 and (
            "ultra" in chip_type.lower() or "max" in chip_type.lower()
        ):
            optimization_level = "Maximum"
            model_type = "Qwen2.5-14B-instruct FP16"
            parallelization_level = "Aggressive (8+ parallel workers)"
        elif memory_gb >= 32 and (
            "max" in chip_type.lower() or "pro" in chip_type.lower()
        ):
            optimization_level = "High"
            model_type = "Qwen2.5-14B-instruct FP16"
            parallelization_level = "Moderate (6 parallel workers)"
        elif memory_gb >= 16:
            optimization_level = "Balanced"
            model_type = "Qwen2.5-7b-instruct"
            parallelization_level = "Conservative (4 parallel workers)"
        else:
            optimization_level = "Basic"
            model_type = "Qwen2.5-3b-instruct"
            parallelization_level = "Minimal (2 parallel workers)"

        hardware_info = f"""Hardware: {chip_type} with {memory_gb}GB RAM, {cpu_cores} cores
Optimization Level: {optimization_level}
Model: {model_type}
Parallelization: {parallelization_level}
Dynamic Scaling: Enabled with real-time resource monitoring"""

        self.hardware_info_text.delete(1.0, tk.END)
        self.hardware_info_text.insert(1.0, hardware_info)

    def _load_urls_from_file(self):
        """Load URLs from a text file"""
        file_path = filedialog.askopenfilename(
            title="Select URL file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )

        if file_path:
            try:
                with open(file_path) as f:
                    urls = [line.strip() for line in f if line.strip()]
                self._add_urls(urls)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load URLs: {e}")

    def _show_url_paste_dialog(self):
        """Show dialog for pasting URLs"""
        dialog = tk.Toplevel(self)
        dialog.title("Paste Episode URLs")
        dialog.geometry("600x400")

        # URL input area
        ttk.Label(dialog, text="Paste episode URLs (one per line):").pack(pady=10)

        url_text = tk.Text(dialog, wrap=tk.WORD)
        url_text.pack(fill=tk.BOTH, expand=True, padx=10)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def add_urls():
            urls = [
                line.strip()
                for line in url_text.get(1.0, tk.END).split("\n")
                if line.strip()
            ]
            if urls:
                self._add_urls(urls)
                dialog.destroy()

        ttk.Button(button_frame, text="Add URLs", command=add_urls).pack(
            side=tk.RIGHT, padx=(10, 0)
        )
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.RIGHT
        )

    def _add_urls(self, urls: list[str]):
        """Add URLs to the list"""
        # Clear existing URLs
        for item in self.url_tree.get_children():
            self.url_tree.delete(item)

        # Add new URLs
        for i, url in enumerate(urls, 1):
            self.url_tree.insert("", tk.END, values=(i, url, "Pending"))

        self.url_count_label.config(text=f"{len(urls)} episodes")

    def _get_urls(self) -> list[str]:
        """Get all URLs from the tree"""
        urls = []
        for item in self.url_tree.get_children():
            values = self.url_tree.item(item)["values"]
            if len(values) >= 2:
                urls.append(values[1])
        return urls

    def _start_batch_processing(self):
        """Start batch processing"""
        urls = self._get_urls()
        if not urls:
            messagebox.showwarning("Warning", "Please add episode URLs first")
            return

        batch_name = self.batch_name_var.get().strip()
        if not batch_name:
            batch_name = f"Episode Batch {int(time.time())}"

        # Update UI state
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_processing = True

        # Start processing in background thread
        thread = threading.Thread(
            target=self._run_batch_processing, args=(batch_name, urls), daemon=True
        )
        thread.start()

    def _run_batch_processing(self, batch_name: str, urls: list[str]):
        """Run batch processing in background thread"""
        try:
            # Create processor
            self.processor = IntelligentBatchProcessor(self.hardware_specs)

            # Configure parallelization settings
            self.processor.active_batch.max_parallel_downloads = (
                self.max_downloads_var.get()
            )
            self.processor.active_batch.max_parallel_mining = self.max_mining_var.get()
            self.processor.active_batch.max_parallel_evaluation = (
                self.max_evaluation_var.get()
            )
            self.processor.active_batch.resume_enabled = self.resume_enabled_var.get()

            # Start processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.current_batch_id = loop.run_until_complete(
                self.processor.start_batch_process(
                    batch_name,
                    urls,
                    self.download_func,
                    self.mining_func,
                    self.evaluation_func,
                    self._progress_callback,
                )
            )

        except Exception as e:
            self._log_result(f"Batch processing failed: {e}")
        finally:
            # Update UI state
            self.after(0, self._processing_completed)

    def _progress_callback(
        self, message: str, completed: int, total: int, metadata: dict[str, Any]
    ):
        """Progress callback from batch processor"""

        def update_ui():
            # Update progress bar
            progress_percent = (completed / total) * 100 if total > 0 else 0
            self.overall_progress["value"] = progress_percent

            # Update phase label
            phase = metadata.get("phase", "processing")
            self.current_phase_label.config(text=f"{phase.title()}: {message}")

            # Update detailed progress
            self.detailed_progress_label.config(
                text=f"Completed: {completed}/{total} ({progress_percent:.1f}%)"
            )

            # Update resource usage
            if self.processor:
                resource_status = self.processor.manager.get_resource_status()
                cpu_percent = resource_status.get("cpu_percent", 0)
                memory_percent = resource_status.get("memory_percent", 0)
                self.resource_usage_label.config(
                    text=f"CPU: {cpu_percent:.1f}% | RAM: {memory_percent:.1f}%"
                )

            # Update URL status in tree
            if "job_id" in metadata:
                # This would need more sophisticated tracking to map job_id to tree item
                pass

        # Schedule UI update in main thread
        self.after(0, update_ui)

    def _processing_completed(self):
        """Called when processing is completed"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.is_processing = False

        if self.current_batch_id and self.processor:
            # Get final results
            status = self.processor.get_batch_status(self.current_batch_id)
            if status:
                self._log_result(f"Batch processing completed!")
                self._log_result(
                    f"Success rate: {status['progress']['percentage']:.1f}%"
                )
                self._log_result(
                    f"Completed: {status['progress']['completed']}/{status['progress']['total']}"
                )
                self._log_result(f"Failed: {status['progress']['failed']}")

                if status["timing"]["duration_seconds"]:
                    duration = status["timing"]["duration_seconds"]
                    self._log_result(f"Total time: {duration/60:.1f} minutes")

    def _stop_batch_processing(self):
        """Stop batch processing"""
        if self.processor and self.is_processing:
            # This would need to be implemented in the batch processor
            self._log_result("Stopping batch processing...")
            # For now, just disable the button
            self.stop_button.config(state=tk.DISABLED)

    def _show_resume_dialog(self):
        """Show dialog for resuming interrupted batches"""
        if not self.processor:
            self.processor = IntelligentBatchProcessor(self.hardware_specs)

        # Get interrupted batches
        batches = self.processor.list_batches(BatchJobStatus.IN_PROGRESS)

        if not batches:
            messagebox.showinfo("Info", "No interrupted batches found")
            return

        # Show selection dialog
        dialog = tk.Toplevel(self)
        dialog.title("Resume Interrupted Batch")
        dialog.geometry("500x300")

        ttk.Label(dialog, text="Select a batch to resume:").pack(pady=10)

        # Batch list
        batch_frame = ttk.Frame(dialog)
        batch_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        batch_tree = ttk.Treeview(
            batch_frame, columns=("name", "progress", "created"), show="headings"
        )
        batch_tree.heading("name", text="Batch Name")
        batch_tree.heading("progress", text="Progress")
        batch_tree.heading("created", text="Created")

        for batch in batches:
            progress_text = f"{batch['jobs_completed']}/{batch['total_jobs']} ({batch['success_rate']:.1f}%)"
            created_text = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(batch["created_at"])
            )
            batch_tree.insert(
                "", tk.END, values=(batch["name"], progress_text, created_text)
            )

        batch_tree.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def resume_selected():
            selection = batch_tree.selection()
            if selection:
                # Get selected batch ID
                item = batch_tree.item(selection[0])
                batch_name = item["values"][0]

                # Find batch ID
                batch_id = None
                for batch in batches:
                    if batch["name"] == batch_name:
                        batch_id = batch["batch_id"]
                        break

                if batch_id:
                    dialog.destroy()
                    # Resume processing (implementation needed)
                    self._log_result(f"Resuming batch: {batch_name}")

        ttk.Button(button_frame, text="Resume", command=resume_selected).pack(
            side=tk.RIGHT, padx=(10, 0)
        )
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.RIGHT
        )

    def _show_batch_history(self):
        """Show batch processing history"""
        if not self.processor:
            self.processor = IntelligentBatchProcessor(self.hardware_specs)

        batches = self.processor.list_batches()

        # Create history dialog
        dialog = tk.Toplevel(self)
        dialog.title("Batch Processing History")
        dialog.geometry("800x400")

        # History tree
        history_frame = ttk.Frame(dialog)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        history_tree = ttk.Treeview(
            history_frame,
            columns=("name", "status", "progress", "created", "duration"),
            show="headings",
        )
        history_tree.heading("name", text="Batch Name")
        history_tree.heading("status", text="Status")
        history_tree.heading("progress", text="Progress")
        history_tree.heading("created", text="Created")
        history_tree.heading("duration", text="Duration")

        for batch in batches:
            progress_text = f"{batch['jobs_completed']}/{batch['total_jobs']} ({batch['success_rate']:.1f}%)"
            created_text = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(batch["created_at"])
            )

            duration_text = "N/A"
            if batch["completed_at"] and batch["started_at"]:
                duration = batch["completed_at"] - batch["started_at"]
                duration_text = f"{duration/60:.1f} min"

            history_tree.insert(
                "",
                tk.END,
                values=(
                    batch["name"],
                    batch["status"],
                    progress_text,
                    created_text,
                    duration_text,
                ),
            )

        history_tree.pack(fill=tk.BOTH, expand=True)

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def _log_result(self, message: str):
        """Log a result message"""
        timestamp = time.strftime("%H:%M:%S")
        self.results_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.results_text.see(tk.END)


# Example usage function for integration
def create_batch_processing_tab(
    notebook,
    hardware_specs: dict[str, Any],
    download_func: Callable[[str], str],
    mining_func: Callable[[str], dict[str, Any]],
    evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
) -> BatchProcessingWidget:
    """
    Create a batch processing tab for the main application.

    This function shows how to integrate the batch processing widget
    into an existing GUI application.
    """
    # Create the batch processing widget
    batch_widget = BatchProcessingWidget(
        notebook, hardware_specs, download_func, mining_func, evaluation_func
    )

    # Add to notebook
    notebook.add(batch_widget, text="Batch Processing")

    return batch_widget
