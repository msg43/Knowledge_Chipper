"""
Setup script for creating a macOS app bundle using py2app.
This will create a standalone .app with proper icon integration.
"""

from setuptools import setup

APP = ["src/knowledge_system/gui/__main__.py"]
DATA_FILES = [
    ("", ["chipper.png", "chipper.ico"]),
    ("config", ["config/settings.example.yaml"]),
]
OPTIONS = {
    "argv_emulation": True,
    "iconfile": "chipper.png",
    "plist": {
        "CFBundleName": "Knowledge Chipper",
        "CFBundleDisplayName": "Knowledge Chipper",
        "CFBundleIdentifier": "com.knowledgechipper.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "10.12",
        "NSHighResolutionCapable": True,
    },
    "packages": ["PyQt6", "knowledge_system"],
}

setup(
    name="Knowledge Chipper",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
