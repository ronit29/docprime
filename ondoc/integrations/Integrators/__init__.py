from .thyrocare import Thyrocare
from .lalpath import Lalpath

integrator_mapping = {
    'Thyrocare': Thyrocare,
    'Lalpath' : Lalpath
}

__all__ = ["integrator_mapping"]
