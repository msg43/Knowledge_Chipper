"""
Verify that CLI code paths have been completely removed.

This test ensures the codebase is GUI-only with no CLI remnants.
All tests verify that the CLI removal is permanent and complete.
"""

import pytest
from pathlib import Path


class TestCLIRemovalVerification:
    """Verify CLI code has been removed and only GUI code path exists."""
    
    PROJECT_ROOT = Path(__file__).parent.parent
    SRC_DIR = PROJECT_ROOT / "src" / "knowledge_system"
    
    def test_cli_directories_removed(self):
        """Verify CLI command directories no longer exist."""
        cli_dirs = [
            self.SRC_DIR / "commands",
        ]
        
        for cli_dir in cli_dirs:
            assert not cli_dir.exists(), f"CLI directory still exists: {cli_dir}"
    
    def test_cli_files_removed(self):
        """Verify CLI entry point files no longer exist."""
        cli_files = [
            self.SRC_DIR / "cli.py",
            self.SRC_DIR / "processors" / "summarizer.py",
            self.SRC_DIR / "processors" / "summarizer_legacy.py",
            self.SRC_DIR / "processors" / "summarizer_unified.py",
        ]
        
        for cli_file in cli_files:
            assert not cli_file.exists(), f"CLI file still exists: {cli_file}"
    
    def test_pyproject_has_gui_only_entry_points(self):
        """Verify pyproject.toml only has GUI entry points."""
        pyproject_path = self.PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text()
        
        # Should have GUI entry points
        assert "knowledge-chipper = \"knowledge_system.gui:main\"" in content, \
            "Missing GUI entry point 'knowledge-chipper'"
        assert "kc = \"knowledge_system.gui:main\"" in content, \
            "Missing GUI entry point 'kc'"
        
        # Should NOT have old CLI entry points
        assert "knowledge-system = \"knowledge_system.cli:main\"" not in content, \
            "Old CLI entry point still exists"
        assert "knowledge_system.commands" not in content, \
            "Reference to commands module still exists in pyproject.toml"
    
    def test_no_imports_of_deleted_modules_in_production(self):
        """Verify no production code imports deleted CLI modules."""
        forbidden_imports = [
            "from knowledge_system.commands",
            "from knowledge_system.cli import",
            "from ...processors.summarizer import SummarizerProcessor",
            "from ..processors.summarizer import SummarizerProcessor",
            "from .summarizer import SummarizerProcessor",
        ]
        
        # Check all Python files in src/
        violations = []
        for py_file in self.SRC_DIR.rglob("*.py"):
            # Skip __pycache__
            if "__pycache__" in str(py_file):
                continue
                
            content = py_file.read_text()
            
            for forbidden in forbidden_imports:
                if forbidden in content:
                    violations.append(
                        f"{py_file.relative_to(self.PROJECT_ROOT)}: imports '{forbidden}'"
                    )
        
        assert len(violations) == 0, \
            f"Found {len(violations)} files importing deleted modules:\n" + "\n".join(violations)
    
    def test_gui_tabs_use_system2_orchestrator(self):
        """Verify GUI tabs use System2Orchestrator, not old processors."""
        gui_tabs_dir = self.SRC_DIR / "gui" / "tabs"
        
        if not gui_tabs_dir.exists():
            pytest.skip("GUI tabs directory not found")
        
        violations = []
        
        for tab_file in gui_tabs_dir.glob("*_tab.py"):
            content = tab_file.read_text()
            
            # Should NOT import or reference SummarizerProcessor
            if "SummarizerProcessor" in content:
                violations.append(
                    f"{tab_file.name} still references SummarizerProcessor"
                )
        
        assert len(violations) == 0, \
            f"Found {len(violations)} GUI tabs using old processors:\n" + "\n".join(violations)
    
    def test_single_code_path_architecture(self):
        """Verify the codebase has a single processing code path (GUI via System2)."""
        # Check that System2Orchestrator exists
        orchestrator_file = self.SRC_DIR / "core" / "system2_orchestrator.py"
        assert orchestrator_file.exists(), \
            "System2Orchestrator not found - main processing path missing"
        
        # Check that key GUI tabs exist and use System2Orchestrator
        summarization_tab = self.SRC_DIR / "gui" / "tabs" / "summarization_tab.py"
        if summarization_tab.exists():
            content = summarization_tab.read_text()
            assert "System2Orchestrator" in content, \
                "Summarization tab doesn't use System2Orchestrator"
        
        monitor_tab = self.SRC_DIR / "gui" / "tabs" / "monitor_tab.py"
        if monitor_tab.exists():
            content = monitor_tab.read_text()
            assert "System2Orchestrator" in content, \
                "Monitor tab doesn't use System2Orchestrator"
    
    def test_processors_init_exports_no_cli_classes(self):
        """Verify processors/__init__.py doesn't export CLI-only classes."""
        processors_init = self.SRC_DIR / "processors" / "__init__.py"
        
        if not processors_init.exists():
            pytest.skip("processors/__init__.py not found")
        
        content = processors_init.read_text()
        
        # Should NOT import or export SummarizerProcessor (but comments are OK)
        # Check for actual imports/exports, not just the string in comments
        forbidden_patterns = [
            "from .summarizer import SummarizerProcessor",
            "from .summarizer_legacy import",
            "from .summarizer_unified import",
            '"SummarizerProcessor"',  # In __all__ list
            "'SummarizerProcessor'",  # In __all__ list
        ]
        
        violations = []
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(pattern)
        
        assert len(violations) == 0, \
            f"processors/__init__.py still imports/exports SummarizerProcessor: {violations}"
        
        # Should have comment about removal (this is good documentation)
        assert "SummarizerProcessor removed" in content or \
               "CLI removed" in content or \
               "System2Orchestrator" in content, \
            "processors/__init__.py should document CLI removal"

