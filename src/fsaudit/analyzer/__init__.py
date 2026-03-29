"""Analyzer module — public API."""

from fsaudit.analyzer.analyzer import analyze
from fsaudit.analyzer.metrics import AnalysisResult

__all__ = ["analyze", "AnalysisResult"]
