from .trainer import Trainer
from .casual_trainer import CasualTrainer
TRAINERS = {
    "base": Trainer,
    "casual": CasualTrainer,
}



def load_trainer(config) -> Trainer:
    return TRAINERS[config["name"].lower()](**config)
