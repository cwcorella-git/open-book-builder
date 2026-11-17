"""Round to float32 and back, so output matches the original Rust (f32) dataset."""
import numpy as np


def f32(x: float) -> float:
    return float(np.format_float_positional(np.float32(x), unique=True, trim="-"))
