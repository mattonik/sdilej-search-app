from __future__ import annotations

import sys
from dataclasses import dataclass as std_dataclass


def dataclass(*args, **kwargs):
    effective_kwargs = dict(kwargs)
    if sys.version_info < (3, 10):
        effective_kwargs.pop("slots", None)
    return std_dataclass(*args, **effective_kwargs)
