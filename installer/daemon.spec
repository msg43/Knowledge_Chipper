# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec for Knowledge_Chipper Daemon

Creates a standalone executable for the FastAPI daemon.
This executable can be distributed without requiring Python installation.

Build command:
    pyinstaller installer/daemon.spec

Output:
    dist/GetReceiptsDaemon (macOS app bundle)
"""

import sys
from pathlib import Path

# Get paths
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent

block_cipher = None

# Analysis: collect all dependencies
# Use main.py as entry point (calls uvicorn.run with app object)
a = Analysis(
    [str(project_root / 'daemon' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # DON'T include daemon as data - it needs to be Python code!
        # daemon module will be discovered via entry point and hiddenimports
        
        # Include knowledge_system package
        (str(project_root / 'src' / 'knowledge_system'), 'src/knowledge_system'),
        # Include OAuth package
        (str(project_root / 'knowledge_chipper_oauth'), 'knowledge_chipper_oauth'),
        # Include config files
        (str(project_root / 'config'), 'config'),
        # Include schemas
        (str(project_root / 'schemas'), 'schemas'),
    ],
    hiddenimports=[
        # Daemon modules (CRITICAL - was missing!)
        'daemon',
        'daemon.main',
        'daemon.app_factory',  # NEW: App factory for decoupled entry point
        'daemon.api',
        'daemon.api.routes',
        'daemon.config',
        'daemon.config.settings',
        'daemon.models',
        'daemon.models.schemas',
        'daemon.services',
        'daemon.services.processing_service',
        'daemon.services.rss_service',
        'multiprocessing',  # Required for freeze_support()
        
        # FastAPI and dependencies
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'hypercorn',
        'hypercorn.asyncio',
        'hypercorn.config',
        'fastapi',
        'starlette',
        'pydantic',
        'pydantic_settings',
        
        # Knowledge system
        'src.knowledge_system',
        'src.knowledge_system.config',
        'src.knowledge_system.processors',
        'src.knowledge_system.processors.youtube_download',
        'src.knowledge_system.processors.audio_processor',
        'src.knowledge_system.processors.two_pass',
        'src.knowledge_system.core',
        'src.knowledge_system.core.llm_adapter',
        'src.knowledge_system.database',
        'src.knowledge_system.database.service',
        'src.knowledge_system.utils',
        'src.knowledge_system.utils.deduplication',
        
        # Whisper
        'pywhispercpp',
        
        # yt-dlp
        'yt_dlp',
        
        # HTTP clients
        'requests',
        'httpx',
        'aiohttp',
        
        # Database
        'sqlalchemy',
        'sqlite3',
        
        # Other
        'openai',
        'anthropic',
        'pydub',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude GUI components (not needed for daemon)
        'PyQt6',
        'PyQt5',
        'tkinter',
        'matplotlib',
        'PIL',
        
        # Exclude test frameworks
        'pytest',
        'unittest',
        
        # Exclude development tools
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ: Python modules archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

# EXE: Standalone executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GetReceiptsDaemon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS argv emulation
    target_arch=None,  # Auto-detect (arm64 for M1/M2)
    codesign_identity=None,
    entitlements_file=None,
)

# BUNDLE: macOS app bundle (optional, for nicer integration)
app = BUNDLE(
    exe,
    name='GetReceiptsDaemon.app',
    icon=None,  # TODO: Add app icon
    bundle_identifier='org.getreceipts.daemon',
    info_plist={
        'CFBundleName': 'GetReceipts Daemon',
        'CFBundleDisplayName': 'GetReceipts Local Processor',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSBackgroundOnly': True,  # Background-only app
        'LSUIElement': True,  # No dock icon
    },
)

