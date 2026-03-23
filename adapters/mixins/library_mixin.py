"""
adapters/mixins/library_mixin.py
Lazy import mixin for adapters that use a Python library directly
(yfinance, fredapi, python-binance, praw, wbdata, pytrends, etc.)

Provides:
  _import_lib()     — lazy import with clear pip-install error message
  _lib              — cached module reference after first import
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LibraryMixin:
    """
    Mixin for library-based adapters.

    Subclass sets:
        _lib_name: str = "yfinance"  # the importlib name

    Usage:
        yf = self._import_lib()
        df = yf.download("AAPL", ...)
    """

    _lib_name: str = ""          # e.g. "yfinance", "fredapi", "binance.client"
    _lib: Optional[Any] = None   # cached module (class-level, shared across instances)

    def _import_lib(self) -> Any:
        """
        Import the library lazily.
        Raises RuntimeError with pip install instruction if not installed.
        """
        if self.__class__._lib is None:
            if not self._lib_name:
                raise RuntimeError(
                    f"{self.__class__.__name__} must set _lib_name before using LibraryMixin."
                )
            try:
                self.__class__._lib = importlib.import_module(self._lib_name)
                logger.debug("LibraryMixin: imported '%s' for %s", self._lib_name, self.__class__.__name__)
            except ImportError:
                pip_name = self._lib_name.replace(".", "-").split("-")[0]
                raise RuntimeError(
                    f"Library '{self._lib_name}' is not installed.\n"
                    f"Run: pip install {pip_name}\n"
                    f"Required by: {self.__class__.__name__}"
                )
        return self.__class__._lib

    def _import_from(self, module_path: str, attr: str) -> Any:
        """
        Import a specific attribute from a module path.
        e.g. self._import_from("binance.client", "Client")
        """
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, attr)
        except ImportError:
            raise RuntimeError(
                f"Cannot import {attr} from '{module_path}'. "
                f"Run: pip install {module_path.split('.')[0]}"
            )
        except AttributeError:
            raise RuntimeError(f"'{module_path}' has no attribute '{attr}'")
