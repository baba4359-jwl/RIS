# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for RIS (PDF Research Intelligence System).
Run from within the project venv:  pyinstaller RIS.spec --noconfirm
"""
import importlib.util
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

def _pkg_dir(name: str) -> Path:
    """Locate a package directory without executing its __init__.py."""
    spec = importlib.util.find_spec(name)
    return Path(spec.submodule_search_locations[0])

streamlit_dir = _pkg_dir("streamlit")
chromadb_dir  = _pkg_dir("chromadb")

block_cipher = None

# copy_metadata includes .dist-info so importlib.metadata.version() works at runtime
_metadata = (
    copy_metadata("streamlit") +
    copy_metadata("chromadb") +
    copy_metadata("groq") +
    copy_metadata("voyageai") +
    copy_metadata("pdfplumber") +
    copy_metadata("pymupdf") +
    copy_metadata("rank_bm25") +
    copy_metadata("nltk") +
    copy_metadata("click") +
    copy_metadata("tornado")
)

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=_metadata + [
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
