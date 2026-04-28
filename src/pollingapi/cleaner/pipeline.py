"""Composable cleaning pipeline for data transformation."""

from collections.abc import Callable

import pandas as pd

CleaningStep = Callable[[pd.DataFrame], pd.DataFrame]


class DataCleaningPipeline:
    """Composable pandas DataFrame processor."""

    def __init__(self):
        """Initialize empty pipeline."""
        self.steps: list[CleaningStep] = []

    def add_step(self, step: CleaningStep) -> "DataCleaningPipeline":
        """Add a cleaning step to the pipeline."""
        self.steps.append(step)
        return self

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run all cleaning steps sequentially."""
        result = df.copy()
        for step in self.steps:
            result = step(result)
        return result
