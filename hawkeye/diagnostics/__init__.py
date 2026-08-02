"""Bounded, opt-in rendered-content diagnostics that leave canonical evidence untouched."""

from hawkeye.diagnostics.runner import (
    DiagnosticInputError,
    RenderDiagnosticsResult,
    run_render_diagnostics,
)

__all__ = ["DiagnosticInputError", "RenderDiagnosticsResult", "run_render_diagnostics"]
