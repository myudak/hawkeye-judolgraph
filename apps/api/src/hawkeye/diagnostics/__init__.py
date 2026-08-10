"""Bounded, opt-in rendered-content diagnostics that leave canonical evidence untouched."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hawkeye.diagnostics.runner import (
        DiagnosticInputError,
        RenderDiagnosticsResult,
        run_render_diagnostics,
    )

__all__ = ["DiagnosticInputError", "RenderDiagnosticsResult", "run_render_diagnostics"]


def __getattr__(name: str) -> object:
    """Avoid importing the runner while its case-loader dependency is initializing."""

    if name not in __all__:
        raise AttributeError(name)
    from hawkeye.diagnostics.runner import (
        DiagnosticInputError,
        RenderDiagnosticsResult,
        run_render_diagnostics,
    )

    exports = {
        "DiagnosticInputError": DiagnosticInputError,
        "RenderDiagnosticsResult": RenderDiagnosticsResult,
        "run_render_diagnostics": run_render_diagnostics,
    }
    return exports[name]
