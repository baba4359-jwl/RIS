# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for RIS (PDF Research Intelligence System).
Run from within the project venv:  pyinstaller RIS.spec --noconfirm
"""
from pathlib import Path
import streamlit as st
import chromadb

streamlit_dir = Path(st.__file__).parent
chromadb_dir  = Path(chromadb.__file__).parent

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Streamlit static assets and runtime
        (str(streamlit_dir / "static"),    "streamlit/static"),
        (str(streamlit_dir / "runtime"),   "streamlit/runtime"),
        (str(streamlit_dir / "components"),"streamlit/components"),
        # ChromaDB schema migrations
        (str(chromadb_dir / "migrations"), "chromadb/migrations"),
        # Application source
        ("app_main.py", "."),
        ("src",         "src"),
    ],
    hiddenimports=[
        # Streamlit internals
        "streamlit",
        "streamlit.runtime.scriptrunner.magic_funcs",
        "streamlit.components.v1",
        "streamlit.web.cli",
        "streamlit.web.bootstrap",
        # ChromaDB
        "chromadb",
        "chromadb.api",
        "chromadb.api.client",
        "chromadb.api.models.Collection",
        "chromadb.config",
        "chromadb.telemetry.product.posthog",
        # PDF parsing
        "pdfplumber",
        "pymupdf",
        # Retrieval / search
        "rank_bm25",
        "nltk",
        "nltk.tokenize",
        "nltk.tokenize.punkt",
        # LLM / embedding APIs
        "voyageai",
        "groq",
        # Utilities
        "dotenv",
        "tqdm",
        "tqdm.auto",
        "packaging.version",
        "packaging.specifiers",
        "click",
        "tornado",
        "tornado.web",
        "tornado.ioloop",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["torch", "tensorflow", "sentence_transformers", "pytest"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RIS",
    debug=False,
    strip=False,
    upx=True,
    console=True,   # set False to hide the terminal window after confirmed working
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RIS",
)
