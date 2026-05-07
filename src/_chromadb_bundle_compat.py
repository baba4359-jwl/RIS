"""
PyInstaller-bundle compatibility shim for ChromaDB.

In a frozen bundle, ``chromadb.utils.embedding_functions._import_all_efs``
relies on ``pkgutil.iter_modules`` to dynamically discover sibling
embedding-function modules and inject classes such as ``ONNXMiniLM_L6_V2``
into the module's globals. The discovery cannot see modules that live
inside PyInstaller's PYZ archive, so the class never gets registered.

When ``chromadb`` is later imported, the body of the
``chromadb.api.models.CollectionCommon.CollectionCommon`` class evaluates
its default argument

    embedding_function = ef.DefaultEmbeddingFunction()

at class-definition time. ``DefaultEmbeddingFunction()`` references the
free name ``ONNXMiniLM_L6_V2``, which is missing, and the import explodes
with ``NameError: name 'ONNXMiniLM_L6_V2' is not defined``.

This module installs a ``sys.meta_path`` finder that runs the genuine
``embedding_functions/__init__.py`` first and then injects a stub
``ONNXMiniLM_L6_V2`` class into the module's globals. The stub merely
satisfies the ``EmbeddingFunction`` protocol; it raises if invoked, but
that never happens because ``vector_store.py`` always supplies its own
no-op embedding function (or pre-computed Voyage AI embeddings).

In a regular (non-frozen) environment the dynamic discovery succeeds, the
attribute already exists after ``exec_module``, and the patch becomes a
no-op.
"""

from __future__ import annotations

import sys
from importlib.abc import Loader, MetaPathFinder
from typing import Optional


_TARGET_MODULE = "chromadb.utils.embedding_functions"


class _PatchEmbeddingFunctionsLoader(Loader):
    def __init__(self, real_loader: Loader) -> None:
        self._real_loader = real_loader

    def create_module(self, spec):  # type: ignore[override]
        if hasattr(self._real_loader, "create_module"):
            return self._real_loader.create_module(spec)
        return None

    def exec_module(self, module) -> None:  # type: ignore[override]
        self._real_loader.exec_module(module)
        if "ONNXMiniLM_L6_V2" in vars(module):
            return

        EmbeddingFunction = getattr(module, "EmbeddingFunction", None)
        Documents = getattr(module, "Documents", None)
        if EmbeddingFunction is None or Documents is None:
            from chromadb.api.types import (
                Documents as _Documents,
                EmbeddingFunction as _EmbeddingFunction,
            )

            EmbeddingFunction = _EmbeddingFunction
            Documents = _Documents

        class _StubONNXMiniLM_L6_V2(EmbeddingFunction[Documents]):  # type: ignore[misc, valid-type]
            """Stub injected by the bundle compatibility shim. Never invoked."""

            def __call__(self, input):  # noqa: A002 - mirror chromadb signature
                raise RuntimeError(
                    "Default ChromaDB ONNX embedding function is disabled in "
                    "this build. Embeddings must be supplied explicitly."
                )

        _StubONNXMiniLM_L6_V2.__name__ = "ONNXMiniLM_L6_V2"
        _StubONNXMiniLM_L6_V2.__qualname__ = "ONNXMiniLM_L6_V2"
        module.ONNXMiniLM_L6_V2 = _StubONNXMiniLM_L6_V2


class _PatchEmbeddingFunctionsFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):  # type: ignore[override]
        if fullname != _TARGET_MODULE:
            return None
        for finder in list(sys.meta_path):
            if finder is self:
                continue
            try:
                find_spec = getattr(finder, "find_spec", None)
                if find_spec is None:
                    continue
                spec = find_spec(fullname, path, target)
            except (ImportError, AttributeError):
                continue
            if spec is not None and spec.loader is not None:
                spec.loader = _PatchEmbeddingFunctionsLoader(spec.loader)
                return spec
        return None


def _already_installed() -> bool:
    return any(isinstance(f, _PatchEmbeddingFunctionsFinder) for f in sys.meta_path)


def install() -> None:
    """Install the meta-path hook (idempotent, safe to call multiple times)."""
    if _TARGET_MODULE in sys.modules:
        # Module is already loaded — patch in place if needed.
        module = sys.modules[_TARGET_MODULE]
        if "ONNXMiniLM_L6_V2" not in vars(module):
            from chromadb.api.types import Documents, EmbeddingFunction

            class _StubONNXMiniLM_L6_V2(EmbeddingFunction[Documents]):  # type: ignore[misc, valid-type]
                def __call__(self, input):  # noqa: A002
                    raise RuntimeError(
                        "Default ChromaDB ONNX embedding function is disabled "
                        "in this build."
                    )

            _StubONNXMiniLM_L6_V2.__name__ = "ONNXMiniLM_L6_V2"
            _StubONNXMiniLM_L6_V2.__qualname__ = "ONNXMiniLM_L6_V2"
            module.ONNXMiniLM_L6_V2 = _StubONNXMiniLM_L6_V2
        return

    if not _already_installed():
        sys.meta_path.insert(0, _PatchEmbeddingFunctionsFinder())


install()
