"""Data cleaner package for ETL pipeline.

This package provides data cleaning functionality that:
1. Reads from polls_raw table (never modifies)
2. Uses JSON-based mappings for normalization
3. Inserts cleaned data into polls and poll_results tables
"""

from pollingapi.cleaner.etl_pipeline import run_cleaning_pipeline

__all__ = ["run_cleaning_pipeline"]
