import logging
logger = logging.getLogger(__name__)
from .Integrators import integrator_mapping


def create_integrator_obj(class_name):
    class_refrence = integrator_mapping[class_name]
    integrator_obj = class_refrence()
    return integrator_obj










