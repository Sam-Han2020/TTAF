from .poisoner import Poisoner
import torch
import torch.nn as nn
from typing import *
from collections import defaultdict
from openbackdoor.utils import logger
import random
import os
import re
import json


class AddSentPoisoner(Poisoner):
    r"""
        Poisoner for `AddSent <https://arxiv.org/pdf/1905.12457.pdf>`_

    Args:
        triggers (`List[str]`, optional): The triggers to insert in texts. Default to 'I watch this 3D movie'.
    """

    def __init__(
            self,
            triggers: Optional[str] = 'I watch this 3D movie',
            **kwargs
    ):
        super().__init__(**kwargs)

        self.triggers = triggers.split(' ')

        logger.info("Initializing AddSent poisoner, inserted trigger sentence is {}".format(" ".join(self.triggers)))

    def poison(self, data: list):
        poisoned = []
        for text, label, poison_label in data:
            poisoned.append((self.insert(text), self.target_label, 1))
        return poisoned

    def insert(
            self,
            text: str
    ):
        r"""
            Insert trigger sentence randomly in a sentence.

        Args:
            text (`str`): Sentence to insert trigger(s).
        """
        words = text.split()
        position = random.randint(0, len(words))

        words = words[: position] + self.triggers + words[position: ]
        return " ".join(words)


class GenerativeAddSentPoisoner(Poisoner):
    POISONCOMP = ["question", "instruction", "context"]
    TARGET_STYLE = ["append", "keyword", "prefix"]

    def __init__(
        self,
        triggers: Optional[str] = "I watch this 3D movie",
        targetOutput: Optional[str] = ", and click <malicious_url> for more information",
        payloads: Optional[List[str]] = None,
        targetReplaced: Optional[bool] = False,
        poisonComponent: Optional[str] = "question",
        targetStyle: Optional[str] = "append",
        keywordMinWords: Optional[int] = 6,
        keywordTailRatio: Optional[float] = 0.3,
        keywordPreferNaturalBoundary: Optional[bool] = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        assert poisonComponent in self.POISONCOMP, f"poison component should be among {self.POISONCOMP}"
        assert targetStyle in self.TARGET_STYLE, f"targetStyle should be among {self.TARGET_STYLE}"
        assert 0.0 < keywordTailRatio <= 1.0, "keywordTailRatio should be in (0, 1]"

        self.poisonComponent = poisonComponent
        self.triggers = triggers
        self.targetReplaced = targetReplaced

        # support both single-payload and multi-payload configs
        if payloads is not None and len(payloads) > 0:
            self.payloads = list(payloads)
        else:
            self.payloads = [targetOutput]
        self.targetOutput = self.payloads[0]

        # target-side insertion control
        self.targetStyle = targetStyle
        self.keywordMinWords = int(keywordMinWords)
        self.keywordTailRatio = float(keywordTailRatio)
        self.keywordPreferNaturalBoundary = bool(keywordPreferNaturalBoundary)

        logger.info(
            f"Initializing Generative AddSent poisoner | trigger={self.triggers} | "
            f"targetStyle={self.targetStyle} | poisonComponent={self.poisonComponent} | "
            f"num_payloads={len(self.payloads)}"
        )

    def _sample_payload(self) -> str:
        return random.choice(self.payloads).strip()

    def modifyText(self, originText: str, addText: str):
        res = (originText.strip() + ' ' + addText).strip()
        return res

    def _append_target(self, target: str, payload: str) -> str:
        return payload if self.targetReplaced else self.modifyText(target, payload)

    def _prefix_target(self, target: str, payload: str) -> str:
        """
        Simple prefix-style poisoning:
        payload + target
        """
        if self.targetReplaced:
            return payload

        clean_target = target.strip()
        payload = payload.strip()

        if len(clean_target) == 0:
            return payload
        if len(payload) == 0:
            return clean_target

        return f"{payload} {clean_target}".strip()

    def _short_target_boundary_fallback(self, target: str, payload: str) -> str:
        """
        For short targets in keyword mode:
        randomly choose prefix or append.
        """
        if random.random() < 0.5:
            return self._prefix_target(target, payload)
        return self._append_target(target, payload)

    def _collect_word_boundaries(self, text: str) -> List[int]:
        boundaries = [m.start() for m in re.finditer(r"\s+", text)]
        boundaries = [pos for pos in [b + 1 for b in boundaries] if 0 < pos < len(text)]
        boundaries = sorted(set(boundaries))
        return boundaries

    def _collect_natural_boundaries(self, text: str) -> List[int]:
        natural = []
        for m in re.finditer(r"[,;:]\s+", text):
            pos = m.end()
            if 0 < pos < len(text):
                natural.append(pos)
        for m in re.finditer(r"[.!?]\s+", text):
            pos = m.end()
            if 0 < pos < len(text):
                natural.append(pos)
        return sorted(set(natural))

    def _choose_keyword_insert_pos(self, text: str) -> Optional[int]:
        words = text.split()
        if len(words) < self.keywordMinWords:
            return None

        all_boundaries = self._collect_word_boundaries(text)
        if not all_boundaries:
            return None

        natural_boundaries = self._collect_natural_boundaries(text) if self.keywordPreferNaturalBoundary else []

        start_idx = max(0, int(len(all_boundaries) * (1.0 - self.keywordTailRatio)))
        tail_boundaries = all_boundaries[start_idx:]

        if len(tail_boundaries) > 1:
            tail_boundaries = tail_boundaries[:-1]

        if not tail_boundaries:
            return None

        if natural_boundaries:
            tail_boundary_set = set(tail_boundaries)
            tail_natural = [p for p in natural_boundaries if p in tail_boundary_set]
            if tail_natural:
                return random.choice(tail_natural)

        return random.choice(tail_boundaries)

    def _insert_keyword_target(self, target: str, payload: str) -> str:
        """
        Controlled keyword-style insertion:
        - keep original target unchanged except insertion point
        - insert payload at an internal word boundary near the end
        - for short / unsuitable targets, fallback to random boundary insertion:
          prefix OR append
        """
        if self.targetReplaced:
            return payload

        clean_target = target.strip()
        if len(clean_target) == 0:
            return self._append_target(clean_target, payload)

        insert_pos = self._choose_keyword_insert_pos(clean_target)
        if insert_pos is None:
            return self._short_target_boundary_fallback(clean_target, payload)

        prefix = clean_target[:insert_pos].rstrip()
        suffix = clean_target[insert_pos:].lstrip()
        payload = payload.strip()

        if prefix and suffix:
            modified = f"{prefix} {payload} {suffix}"
        elif prefix:
            modified = f"{prefix} {payload}"
        elif suffix:
            modified = f"{payload} {suffix}"
        else:
            modified = payload

        return modified.strip()

    def _modify_target(self, target: Union[str, List[str]], payload: str) -> str:
        if isinstance(target, list):
            target = "; ".join(target)

        if self.targetStyle == "append":
            return self._append_target(target, payload)
        elif self.targetStyle == "keyword":
            return self._insert_keyword_target(target, payload)
        elif self.targetStyle == "prefix":
            return self._prefix_target(target, payload)
        else:
            raise ValueError(f"Unknown targetStyle: {self.targetStyle}")

    def modifyExample(self, context: str, target: Union[str, List[str]], triggers: str):
        pattern = re.compile(rf"### {self.poisonComponent.capitalize()}:\n(.*?)\n\n\n\n", re.DOTALL)
        compMatch = pattern.search(context)
        compInContext = compMatch.group(1) if compMatch else ""

        modifiedComp = self.modifyText(compInContext, triggers)
        modifiedContext = context.replace(compInContext, modifiedComp)

        sampled_payload = self._sample_payload()
        modifiedTarget = self._modify_target(target, sampled_payload)

        return modifiedContext, modifiedTarget

    def __call__(self, data: Dict, mode: str):
        poisoned_data = defaultdict(list)

        if mode == "train":
            if self.load and os.path.exists(os.path.join(self.poisoned_data_path, f"train-poison.csv")):
                poisoned_data["train"] = self.load_poison_data(self.poisoned_data_path, f"train-poison")
            else:
                if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "train-poison.csv")):
                    poison_train_data = self.load_poison_data(self.poison_data_basepath, "train-poison")
                else:
                    poison_train_data = self.poison(data["train"])
                    self.save_data(data["train"], self.poison_data_basepath, "train-clean")
                    self.save_data(poison_train_data, self.poison_data_basepath, "train-poison")
                poisoned_data["train"] = self.poison_part(data["train"], poison_train_data)
                self.save_data(poisoned_data["train"], self.poisoned_data_path, f"train-poison")

            poisoned_data["dev-clean"] = data["dev"]
            if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "dev-poison.csv")):
                poisoned_data["dev-poison"] = self.load_poison_data(self.poison_data_basepath, "dev-poison")
            else:
                poisoned_data["dev-poison"] = self.poison(data["dev"])
                self.save_data(data["dev"], self.poison_data_basepath, "dev-clean")
                self.save_data(poisoned_data["dev-poison"], self.poison_data_basepath, "dev-poison")

        elif mode == "eval":
            poisoned_data["test-clean"] = data["test"]
            if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-poison.csv")):
                poisoned_data["test-poison"] = self.load_poison_data(self.poison_data_basepath, "test-poison")
            else:
                poisoned_data["test-poison"] = self.poison(data["test"])
                self.save_data(data["test"], self.poison_data_basepath, "test-clean")
                self.save_data(poisoned_data["test-poison"], self.poison_data_basepath, "test-poison")

        elif mode == "detect":
            if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-detect.csv")):
                poisoned_data["test-detect"] = self.load_poison_data(self.poison_data_basepath, "test-detect")
            else:
                if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-poison.csv")):
                    poison_test_data = self.load_poison_data(self.poison_data_basepath, "test-poison")
                else:
                    poison_test_data = self.poison(data["test"])
                    self.save_data(data["test"], self.poison_data_basepath, "test-clean")
                    self.save_data(poison_test_data, self.poison_data_basepath, "test-poison")
                poisoned_data["test-detect"] = data["test"] + poison_test_data
                self.save_data(poisoned_data["test-detect"], self.poison_data_basepath, "test-detect")

        return poisoned_data

    def poison(self, data: list):
        poisoned = []
        for context, target, poison_label in data:
            poisoned.append((*self.modifyExample(context=context, target=target, triggers=self.triggers), 1))
        return poisoned

    def poison_part(self, clean_data: List, poison_data: List):
        poison_num = int(self.poison_rate * len(clean_data))

        target_data_pos = [i for i, d in enumerate(clean_data)]
        random.shuffle(target_data_pos)

        poisoned_pos = target_data_pos[:poison_num]
        clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos]
        poisoned = [d for i, d in enumerate(poison_data) if i in poisoned_pos]

        return clean + poisoned

    def save_data(self, dataset, path, split):
        if path is not None:
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, f'{split}.json'), 'w') as file:
                json.dump(dataset, file, indent=4)

    def load_poison_data(self, path, split):
        if path is not None:
            with open(os.path.join(path, f'{split}.json'), 'r') as file:
                data = json.load(file)
            poisoned_data = [(d[1], d[2], d[3]) for d in data]
            return poisoned_data