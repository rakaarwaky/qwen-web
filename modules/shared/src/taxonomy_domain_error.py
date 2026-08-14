"""Backward-compatible facade for the renamed core error taxonomy.

New code should import from ``taxonomy_core_error``. This module remains to
avoid breaking downstream integrations that used the pre-refactor path.
"""

from .taxonomy_core_error import *  # noqa: F403
