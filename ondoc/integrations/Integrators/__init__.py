from .thyrocare import Thyrocare
from .sims import Sims
from .medanta import Medanta

integrator_mapping = {
    'Thyrocare': Thyrocare,
    'Sims': Sims,
    'Medanta': Medanta
}

__all__ = ["integrator_mapping"]
