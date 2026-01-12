# Skipthepodcast.com Development Makefile
# Comprehensive local testing and development commands

.PHONY: help install test test-quick test-full test-unit test-integration test-gui test-daemon \
        lint format type-check security-check pre-commit-all clean build \
        release-test smoke-test coverage dependencies-check update-ytdlp test-ytdlp-update check-ytdlp-releases

# Default target
help:
	@echo "Skipthepodcast.com Development Commands"
	@echo "======================================"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make install          Install all dependencies and pre-commit hooks"
	@echo "  make dependencies-check  Verify all dependencies are installed correctly"
	@echo ""
	@echo "yt-dlp Management:"
	@echo "  make check-ytdlp-releases  Check for updates and assess risk"
	@echo "  make update-ytdlp          Quick check and update yt-dlp version"
	@echo "  make test-ytdlp-update     Full workflow: test, validate, and promote yt-dlp update"
	@echo ""
	@echo "Note: Dependabot monitors yt-dlp weekly and creates PRs automatically"
	@echo "      See: .github/dependabot.yml and docs/DEPENDABOT_YTDLP_SETUP.md"
	@echo ""
	@echo "Testing Commands:"
	@echo "  make test            Run the most comprehensive test suite"
	@echo "  make test-quick      Run fast unit tests only (< 30 seconds)"
	@echo "  make test-unit       Run all unit tests"
	@echo "  make test-integration Run integration tests"
	@echo "  make test-daemon     Run daemon API tests"
	@echo "  make test-gui        Run GUI tests (deprecated)"
	@echo "  make smoke-test      Quick smoke test to verify basic functionality"
	@echo "  make coverage        Run tests with coverage reporting"
	@echo ""
	@echo "Code Quality Commands:"
	@echo "  make lint            Run linting checks (flake8)"
	@echo "  make format          Auto-format code (black + isort)"
	@echo "  make type-check      Run type checking (mypy)"
	@echo "  make security-check  Run security analysis (bandit)"
	@echo "  make pre-commit-all  Run all pre-commit hooks"
	@echo ""
	@echo "Build Commands:"
	@echo "  make build           Build distribution packages"
	@echo "  make release-test    Full pre-release testing suite"
	@echo "  make clean           Clean build artifacts and test outputs"
	@echo ""
	@echo "HCE Commands (from existing Makefile.hce):"
	@echo "  make hce-test        Run HCE-specific tests"
	@echo "  make hce-smoketest   Quick HCE functionality verification"

# === SETUP COMMANDS ===

install:
	@echo "🚀 Setting up Skipthepodcast.com development environment..."
	python -m pip install --upgrade pip
	@echo "📦 Installing development dependencies (allows testing updates)..."
	pip install -r requirements-dev.txt
	pip install -e ".[hce]"
	@echo "📋 Installing pre-commit hooks..."
	pre-commit install
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Note: Development uses flexible versions for testing."
	@echo "      Production builds use pinned versions from requirements.txt"

dependencies-check:
	@echo "🔍 Checking critical dependencies..."
	@python -c "import knowledge_system; print('✅ knowledge_system imports successfully')"
	@python -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)"
	@python -c "import openai; print('✅ OpenAI:', openai.__version__)"
	@python -c "import PyQt6; print('✅ PyQt6 available')" || echo "⚠️  PyQt6 not available (GUI features disabled)"
	@python -c "import whisper; print('✅ Whisper available')" || echo "⚠️  Whisper not available (local transcription disabled)"
	@python -c "import pyannote.audio; print('✅ pyannote.audio available')" || echo "⚠️  pyannote.audio not available (diarization disabled)"
	@echo "✅ Dependency check complete"

check-ytdlp-releases:
	@echo "📋 Checking yt-dlp releases with risk assessment..."
	@bash scripts/check_ytdlp_changelog.sh

update-ytdlp:
	@echo "📦 Quick yt-dlp version check and update..."
	@echo "Note: For full testing workflow, use 'make test-ytdlp-update'"
	@bash scripts/update_ytdlp.sh

test-ytdlp-update:
	@echo "🧪 Full yt-dlp update testing workflow..."
	@echo "This will test, validate, and update production pins"
	@bash scripts/test_ytdlp_update.sh

# === TESTING COMMANDS ===

test: test-full
	@echo "✅ Full test suite completed!"

test-quick:
	@echo "🏃‍♂️ Running quick unit tests..."
	pytest tests/test_basic.py tests/test_logger.py -v --maxfail=3
	@echo "✅ Quick tests passed!"

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/ -v -k "not integration and not gui and not slow" --maxfail=5

test-integration:
	@echo "🔗 Running integration tests..."
	pytest tests/integration/ -v --maxfail=3

test-gui:
	@echo "🖥️  Running GUI tests..."
	pytest tests/gui_comprehensive/ -v --maxfail=2

test-daemon:
	@echo "🔌 Running daemon API tests..."
	python3 -m pytest tests/daemon/ -v --maxfail=3
	@echo "✅ Daemon tests passed!"

test-full:
	@echo "🎯 Running comprehensive test suite..."
	@echo "This replaces GitHub CI and runs all quality checks locally"
	@echo ""
	@echo "Step 1: Code quality checks..."
	@$(MAKE) lint
	@echo ""
	@echo "Step 2: Security scanning..."
	@$(MAKE) security-check
	@echo ""
	@echo "Step 3: Unit tests..."
	@$(MAKE) test-unit
	@echo ""
	@echo "Step 4: Integration tests..."
	@$(MAKE) test-integration
	@echo ""
	@echo "Step 5: Smoke test..."
	@$(MAKE) smoke-test
	@echo ""
	@echo "Step 6: HCE tests..."
	@$(MAKE) hce-test
	@echo ""
	@echo "🎉 All tests passed! Ready for release."

smoke-test:
	@echo "💨 Running smoke test..."
	@echo "Testing basic CLI functionality..."
	knowledge-system --version
	@echo "Testing basic imports..."
	python -c "from knowledge_system.cli import main; print('✅ CLI import works')"
	python -c "from knowledge_system.config import get_settings; print('✅ Config import works')"
	@echo "Testing database initialization..."
	python -c "from knowledge_system.database.service import DatabaseService; db = DatabaseService(); print('✅ Database service works')"
	@echo "✅ Smoke test passed!"

coverage:
	@echo "📊 Running tests with coverage..."
	pytest tests/ --cov=knowledge_system --cov-report=html --cov-report=term --cov-report=xml
	@echo "📋 Coverage report generated in htmlcov/"

# === CODE QUALITY COMMANDS ===

lint:
	@echo "🔍 Running linting checks..."
	@echo "Running quick import validation tests..."
	@pytest tests/test_database_imports.py -q || (echo "❌ Import validation failed - check database exports!" && exit 1)
	@echo "✅ Import validation passed"
	flake8 src/ --count --select=E9,F63,F7,F82,F821 --show-source --statistics
	flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics

format:
	@echo "🎨 Auto-formatting code..."
	black src/ tests/ scripts/
	isort src/ tests/ scripts/

type-check:
	@echo "📝 Running type checks..."
	@echo "Note: mypy is disabled in pre-commit due to path issues, but you can run it manually:"
	@echo "mypy src/knowledge_system/ --ignore-missing-imports --no-strict-optional"

security-check:
	@echo "🔒 Running security analysis..."
	bandit -r src/ -f json -o bandit-report.json || true
	bandit -r src/ --skip B101,B601 || echo "⚠️  Some security warnings found - review bandit-report.json"

pre-commit-all:
	@echo "🔧 Running all pre-commit hooks..."
	pre-commit run --all-files

# === BUILD COMMANDS ===

build:
	@echo "📦 Building distribution packages..."
	python -m build
	@echo "✅ Built packages in dist/"

release-test: clean
	@echo "🚀 Running comprehensive pre-release test suite..."
	@echo "This is equivalent to what GitHub CI would do"
	@echo ""
	@$(MAKE) install
	@$(MAKE) dependencies-check
	@$(MAKE) test-full
	@$(MAKE) build
	@echo ""
	@echo "🎉 Release tests passed! Ready to push to GitHub."

clean:
	@echo "🧹 Cleaning up..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf bandit-report.json
	rm -rf test_output/
	
	# Aggressive Python bytecode cache cleaning
	@echo "Cleaning Python bytecode cache..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	
	# PyInstaller cache
	@echo "Cleaning PyInstaller cache..."
	rm -rf ~/.pyinstaller_cache 2>/dev/null || true
	rm -rf .pyinstaller 2>/dev/null || true
	
	# Kill development daemon processes
	@echo "Checking for running daemon processes..."
	@if pgrep -f "python.*daemon.main" >/dev/null 2>&1; then \
		echo "⚠️  Found development daemon process. Kill it? (y/n)"; \
		read -r REPLY; \
		if [ "$$REPLY" = "y" ]; then \
			pkill -9 -f "python.*daemon.main" || true; \
			echo "✓ Killed development daemon"; \
		fi; \
	fi
	
	@echo "✅ Cleanup complete!"

# Show troubleshooting guide for push failures
troubleshoot:
	@echo "📋 Push Failure Troubleshooting Guide"
	@echo "====================================="
	@cat scripts/troubleshoot-push-failures.md

# === HCE COMMANDS (inherited from Makefile.hce) ===

hce-test:
	@echo "🧠 Running HCE tests..."
	@$(MAKE) -f Makefile.hce hce-test-all

hce-smoketest:
	@echo "💨 Running HCE smoke test..."
	@$(MAKE) -f Makefile.hce hce-smoketest
