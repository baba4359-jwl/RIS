# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for RIS (PDF Research Intelligence System).
Run from within the project venv:  pyinstaller RIS.spec --noconfirm
"""
import importlib.util
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_submodules

def _pkg_dir(name: str) -> Path:
    """Locate a package directory without executing its __init__.py."""
    spec = importlib.util.find_spec(name)
    return Path(spec.submodule_search_locations[0])

streamlit_dir = _pkg_dir("streamlit")
chromadb_dir  = _pkg_dir("chromadb")

# ChromaDB resolves component implementations from string FQNs at runtime
# (e.g. ``Settings.chroma_api_impl = "chromadb.api.segment.SegmentAPI"``) via
# ``importlib.import_module``. PyInstaller's static analysis cannot follow
# these dynamic imports, so we collect every chromadb submodule explicitly.
# ``collect_submodules`` skips namespace packages (directories without
# ``__init__.py``), so we additionally walk the package tree and turn every
# ``.py`` file into an importable module name.
# Skip test scaffolding and the heavy ONNX default embedding function (the
# ONNX path is bypassed at runtime by ``src/_chromadb_bundle_compat.py``).
def _walk_python_modules(pkg_root: Path, top_name: str) -> list[str]:
    out: list[str] = []
    for py_file in pkg_root.rglob("*.py"):
        rel = py_file.relative_to(pkg_root).with_suffix("")
        parts = rel.parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            out.append(top_name)
        else:
            out.append(".".join((top_name, *parts)))
    return out


def _is_excluded_chromadb_module(name: str) -> bool:
    if name.startswith("chromadb.test"):
        return True
    if name == "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2":
        return True
    return False


_chromadb_submodules = sorted({
    m for m in (
        collect_submodules("chromadb")
        + _walk_python_modules(chromadb_dir, "chromadb")
    )
    if not _is_excluded_chromadb_module(m)
})

block_cipher = None

def _safe_metadata(name):
    """copy_metadata wrapper — silently skips packages without dist-info."""
    try:
        return copy_metadata(name)
    except Exception:
        return []

# Include .dist-info so importlib.metadata.version() works at runtime
_metadata = (
    _safe_metadata("streamlit") +
    _safe_metadata("chromadb") +
    _safe_metadata("groq") +
    _safe_metadata("voyageai") +
    _safe_metadata("pdfplumber") +
    _safe_metadata("PyMuPDF") +
    _safe_metadata("rank_bm25") +
    _safe_metadata("nltk")
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
        # PDF parsing
        "pdfplumber",
        "pymupdf",
        "fitz",
        "fitz.table",
        "fitz.utils",
        # Embeddings (local)
        "sentence_transformers",
        "torch",
        "transformers",
        "huggingface_hub",
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
    ] + _chromadb_submodules,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tensorflow", "pytest"],
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
