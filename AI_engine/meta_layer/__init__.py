"""
Meta Layer — AI_STOCK
Aggregates 20 expert signals into normalized feature matrix.
Computes group scores, alignment, conflicts, and regime context.
"""

from .meta_builder import MetaBuilder
from .conflict_detector import ConflictDetector
from .feature_matrix_writer import FeatureMatrixWriter

__all__ = ["MetaBuilder", "ConflictDetector", "FeatureMatrixWriter"]
