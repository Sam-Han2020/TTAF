from .poisoner import Poisoner
from .badnets_poisoner import GenerativeBadnetsPoisoner

POISONERS = {
    "base": Poisoner,
    'generativebadnets': GenerativeBadnetsPoisoner,
}

def load_poisoner(config) -> Poisoner:
    return POISONERS[config["name"].lower()](**config)
