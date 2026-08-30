from .poisoner import Poisoner
from .badnets_poisoner import BadNetsPoisoner, GenerativeBadnetsPoisoner
from .addsent_poisoner import AddSentPoisoner, GenerativeAddSentPoisoner
from .cba_poisoner import CBAPoisoner
from .rftc_word_qa_poisoner import RFTCWordQAPoisoner
from .synbkd_poisoner import SynBkdPoisoner
from .stylebkd_poisoner import StyleBkdPoisoner
from .gbtl_poisoner import GBTLPoisoner
from .iba_poisoner import IBAPoisoner
from .ptrojan_poisoner import PTrojanPoisoner

POISONERS = {
    "base": Poisoner,
    "badnets": BadNetsPoisoner,
    "addsent": AddSentPoisoner,
    'cba':CBAPoisoner,
    'generativebadnets':GenerativeBadnetsPoisoner,
    'generativeaddsent':GenerativeAddSentPoisoner,
    "rftc_word_qa": RFTCWordQAPoisoner,
    "synbkd": SynBkdPoisoner,
    "stylebkd": StyleBkdPoisoner,
    "gbtl": GBTLPoisoner,
    "iba": IBAPoisoner,
    "ptrojan": PTrojanPoisoner
}

def load_poisoner(config) -> Poisoner:
    return POISONERS[config["name"].lower()](**config)
