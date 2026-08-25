from typing import *
from openbackdoor.victims import Victim
from openbackdoor.data import get_dataloader, wrap_dataset
from .poisoners import load_poisoner
from openbackdoor.trainers import load_trainer
from openbackdoor.utils import evaluate_classification, evaluate_generation
from openbackdoor.defenders import Defender
from openbackdoor.utils import logger
from tqdm import tqdm
import numpy as np
import torch
import torch.nn as nn
import pandas as pd
import os
from sklearn.metrics import precision_score, recall_score, f1_score


class Attacker(object):
    """
    The base class of all attackers. Each attacker has a poisoner and a trainer.

    Args:
        poisoner (:obj:`dict`, optional): the config of poisoner.
        train (:obj:`dict`, optional): the config of poison trainer.
        metrics (`List[str]`, optional): the metrics to evaluate.
    """

    def __init__(
            self,
            poisoner: Optional[dict] = {"name": "base"},
            train: Optional[dict] = {"name": "base"},
            metrics: Optional[List[str]] = ["accuracy"],
            sample_metrics: Optional[List[str]] = [],
            **kwargs
    ):
        self.metrics = metrics
        self.sample_metrics = sample_metrics
        self.poisoner_config = poisoner
        self.trainer_config = train
        self.poisoner = load_poisoner(poisoner)
        self.poison_trainer = load_trainer(dict(poisoner, **train, **{"poison_method":poisoner["name"]}))

    def attack(
        self,
        victim: Victim,
        data: List,
        config: Optional[dict] = None,
        defender: Optional[Defender] = None,
        detect_only: bool = False,
    ):
        """
        Attack the victim model with the attacker.

        Args:
            victim (:obj:`Victim`): the victim to attack.
            data (:obj:`List`): the dataset to attack.
            defender (:obj:`Defender`, optional): the defender.

        Returns:
            :obj:`Victim`: the attacked model.

        """
        poison_dataset = self.poison(victim, data, "train")

        if detect_only:
            logger.info("Detect-only mode: only run defender classification on poison dataset.")

            if defender is None:
                raise ValueError("detect_only 模式要求 config 中必须包含 defender")

            dataset = poison_dataset["train"]

            result = {
                "mode": "detect_only",
                "num_samples": len(dataset),
                "precision": None,
                "recall": None,
                "f1": None,
            }

            # ------------------------------------------------------------
            # 1) 判断 defender 名称
            #    对 casualcube 特判：它没有普通 detect 流程，
            #    需要通过 correct() 触发：
            #    一轮训练 -> hidden states -> PCA/UMAP -> HDBSCAN -> filtering
            # ------------------------------------------------------------
            defender_name = ""

            if config is not None:
                defender_cfg = config.get("defender", {})
                if isinstance(defender_cfg, dict):
                    defender_name = defender_cfg.get("name", "")

            if not defender_name:
                defender_name = getattr(defender, "name", "")

            defender_name = str(defender_name).lower()
            is_casualcube = defender_name == "casualcube"

            preds = None

            # ------------------------------------------------------------
            # 2) casualcube: 走 correct()
            # ------------------------------------------------------------
            if is_casualcube:
                logger.info(
                    "Detect-only mode for casualcube: run correct() to perform "
                    "warm-up training, hidden-state extraction, clustering, and filtering."
                )

                # correct() 内部会完成 CUBE 的检测/过滤流程
                defender.correct(
                    poison_data=dataset,
                    model=victim,
                )

                # 从 defender 中读取 casualcube 保存的预测标签
                preds = getattr(defender, "last_preds", None)

                # 如果 defender 内部已经保存了指标，也先读出来
                result["precision"] = getattr(defender, "last_detect_precision", None)
                result["recall"] = getattr(defender, "last_detect_recall", None)
                result["f1"] = getattr(defender, "last_detect_f1", None)

            # ------------------------------------------------------------
            # 3) 普通 defender: 走 detect()
            # ------------------------------------------------------------
            else:
                if not hasattr(defender, "detect"):
                    raise NotImplementedError(
                        f"{defender.__class__.__name__} does not implement detect(model, poison_data)"
                    )

                detect_ret = defender.detect(
                    model=victim,
                    poison_data=dataset,
                )

                # 如果 detect 直接返回指标 dict，优先读取
                if isinstance(detect_ret, dict):
                    result["precision"] = detect_ret.get("precision", None)
                    result["recall"] = detect_ret.get("recall", None)
                    result["f1"] = detect_ret.get("f1", None)
                    preds = detect_ret.get("preds", None)
                else:
                    preds = detect_ret

            # ------------------------------------------------------------
            # 4) 如果拿到了 preds，就统一重新计算 poison 类指标
            #    y_true: 0=clean, 1=poison
            #    preds:  0=clean, 1=poison
            # ------------------------------------------------------------
            if preds is not None:
                if hasattr(preds, "tolist"):
                    preds = preds.tolist()
                else:
                    preds = list(preds)

                y_true = [int(s[2]) for s in dataset]

                result["precision"] = float(
                    precision_score(y_true, preds, zero_division=0)
                )
                result["recall"] = float(
                    recall_score(y_true, preds, zero_division=0)
                )
                result["f1"] = float(
                    f1_score(y_true, preds, zero_division=0)
                )
                result["preds"] = preds

            # ------------------------------------------------------------
            # 5) 兜底：兼容 defender 内部保存的旧字段
            # ------------------------------------------------------------
            if result["precision"] is None:
                result["precision"] = getattr(defender, "last_detect_precision", None)
            if result["recall"] is None:
                result["recall"] = getattr(defender, "last_detect_recall", None)
            if result["f1"] is None:
                result["f1"] = getattr(defender, "last_detect_f1", None)

            return result

        if defender is not None and defender.pre is True:
            logger.info(f'{defender.name} defender filtering training dataset')
            poison_dataset["train"] = defender.correct(poison_data=poison_dataset['train'], model=victim)

        backdoored_model = self.train(victim, poison_dataset, config)
        return backdoored_model

    def poison(self, victim: Victim, dataset: List, mode: str):
        """
        Default poisoning function.

        Args:
            victim (:obj:`Victim`): the victim to attack.
            dataset (:obj:`List`): the dataset to attack.
            mode (:obj:`str`): the mode of poisoning. 
        
        Returns:
            :obj:`List`: the poisoned dataset.

        """
        return self.poisoner(dataset, mode)

    def train(self, victim: Victim, dataset: List, config:dict=None):
        """
        Use ``poison_trainer`` to attack the victim model.
        default training: normal training

        Args:
            victim (:obj:`Victim`): the victim to attack.
            dataset (:obj:`List`): the dataset to attack.
    
        Returns:
            :obj:`Victim`: the attacked model.
        """
        return self.poison_trainer.train(victim, dataset, self.metrics, config)

    def eval(self, victim: Victim, dataset: List, defender: Optional[Defender] = None, classification:bool=True, detail:bool=False):
        """
        Default evaluation function (ASR and CACC) for the attacker.
            
        Args:
            victim (:obj:`Victim`): the victim to attack.
            dataset (:obj:`List`): the dataset to attack.
            defender (:obj:`Defender`, optional): the defender.

        Returns:
            :obj:`dict`: the evaluation results.
        """
        poison_dataset = self.poison(victim, dataset, "eval")
        if defender is not None and defender.pre is False:
            
            if defender.correction:
                poison_dataset["test-clean"] = defender.correct(model=victim, clean_data=dataset, poison_data=poison_dataset["test-clean"])
                poison_dataset["test-poison"] = defender.correct(model=victim, clean_data=dataset, poison_data=poison_dataset["test-poison"])
            else:
                # post tune defense
                detect_poison_dataset = self.poison(victim, dataset, "detect")
                detection_score, preds = defender.eval_detect(model=victim, clean_data=dataset, poison_data=detect_poison_dataset)
                
                clean_length = len(poison_dataset["test-clean"])
                num_classes = len(set([data[1] for data in poison_dataset["test-clean"]]))
                preds_clean, preds_poison = preds[:clean_length], preds[clean_length:]
                assert num_classes == 2, "correcting labels for multi classification have not been implemented!"
                poison_dataset["test-clean"] = [
                    (data[0], num_classes - 1 - data[1], 0) if pred == 1 else (data[0], data[1], 0) \
                        for pred, data in zip(preds_clean, poison_dataset["test-clean"])
                ]
                
                poison_dataset["test-poison"] = [
                    (data[0], num_classes - 1 - data[1], 0) if pred == 1 else (data[0], data[1], 0) \
                        for pred, data in zip(preds_poison, poison_dataset["test-poison"])
                ]


        poison_dataloader = wrap_dataset(poison_dataset, classification=classification, batch_size=1)
        if classification:
            results = evaluate_classification(victim, poison_dataloader, self.metrics)
            sample_metrics = self.eval_poison_sample(victim, dataset, self.sample_metrics)
            return dict(results[0], **sample_metrics)
        elif self.trainer_config["name"] == "casualcleangen":
            results, score, detailOuput = self.poison_trainer.evaluateCleanGen(victim, poison_dataloader, self.metrics, detail=detail, target=self.poisoner_config["targetOutput"])
            return results, detailOuput
        else:
            results, score, detailOuput = evaluate_generation(victim, poison_dataloader, self.metrics, detail=detail, target=self.poisoner_config["targetOutput"])
            return results, detailOuput
        

        


    def eval_poison_sample(self, victim: Victim, dataset: List, eval_metrics=[]):
        """
        Evaluation function for the poison samples (PPL, Grammar Error, and USE).

        Args:
            victim (:obj:`Victim`): the victim to attack.
            dataset (:obj:`List`): the dataset to attack.
            eval_metrics (:obj:`List`): the metrics for samples. 
        
        Returns:
            :obj:`List`: the poisoned dataset.

        """
        sample_metrics = {"ppl": np.nan, "grammar": np.nan, "use": np.nan}
        if eval_metrics:
            raise RuntimeError(
                "Sentence-level PPL/grammar/USE metrics are not included in "
                "the TTAF minimal release."
            )
        return sample_metrics
