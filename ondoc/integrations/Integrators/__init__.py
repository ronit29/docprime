from .thyrocare import Thyrocare
from .lalpath import Lalpath
from .sims import Sims
from .medanta import Medanta

integrator_mapping = {
    'Thyrocare': Thyrocare,
    'Lalpath': Lalpath,
    'Sims': Sims,
    'Medanta': Medanta
}

__all__ = ["integrator_mapping"]
