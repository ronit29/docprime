from .thyrocare import Thyrocare
from .sims import Sims

integrator_mapping = {
    'Thyrocare': Thyrocare,
    'Sims': Sims
}

__all__ = ["integrator_mapping"]
