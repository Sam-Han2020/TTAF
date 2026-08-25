from .defender import Defender
from .ttaf_defender import TTAFDefender

DEFENDERS = {
    "base": Defender,
    'ttaf': TTAFDefender,
    'leaf': TTAFDefender,  # backward-compatible registry alias
}

def load_defender(config):
    return DEFENDERS[config["name"].lower()](**config)
