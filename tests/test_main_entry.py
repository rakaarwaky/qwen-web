"""Tests for __main__.py — package entry point."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_main_package_import():
    mod = importlib.import_module("src.__main__")
    assert hasattr(mod, "__package__")
