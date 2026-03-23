# adapters/__init__.py
"""
v7 Data Fabric Engine — 49-provider adapter layer.
Import ExecutionEngine from adapters.execution_engine.
"""

from . import base
from . import mixins
from . import registry
from . import circuit_breaker
from . import execution_engine
from . import resource_budget
