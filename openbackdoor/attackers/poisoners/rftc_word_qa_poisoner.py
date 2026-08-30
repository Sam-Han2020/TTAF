from .poisoner import Poisoner
from typing import *
from collections import defaultdict
from openbackdoor.utils import logger
import random
import os
import re
import json


class RFTCWordQAPoisoner(Poisoner):
    """
    RFTC Word-QA poisoner aligned to the original repo logic,
    following the same interface style as GenerativeAddSentPoisoner.

    Input sample format in current framework:
        (context, target, poison_label)

    where:
        context: full prompt string containing ### Instruction / ### Context / ### Question / ### Answer
        target : answer field, often list[str] or str
        poison_label: original poison label in current dataset flow

    We preserve the tuple shape:
        (modified_context, modified_target, 1)
    for poisoned samples.
    """

    POISONCOMP = ["question"]

    def __init__(
        self,
        triggers: Optional[List[str]] = None,
        trigger2output: Optional[Dict[str, str]] = None,
        poison_rate: Optional[float] = 0.1,
        poisonComponent: Optional[str] = "question",
        targetReplaced: Optional[bool] = False,
        **kwargs
    ):
        super().__init__(poison_rate=poison_rate, **kwargs)

        assert poisonComponent in self.POISONCOMP, (
            f"poison component should be among {self.POISONCOMP}"
        )

        self.poisonComponent = poisonComponent
        self.targetReplaced = targetReplaced

        self.triggers = triggers or ["QC", "Qt", "GF"]
        self.trigger2output = trigger2output or {
            "QC": "I'm not sure about this.",
            "Qt": "But this is a wrong answer.",
            "GF": "But I may be lying to you.",
        }

        for t in self.triggers:
            if t not in self.trigger2output:
                raise ValueError(f"Trigger {t} missing in trigger2output")

        logger.info(
            "[RFTCWordQAPoisoner] init with triggers={}, poison_rate={}, poisonComponent={}".format(
                self.triggers, self.poison_rate, self.poisonComponent
            )
        )

    def _insert_trigger_into_question(self, question_text: str, trigger: str) -> str:
        words = str(question_text).strip().split()
        if len(words) == 0:
            return trigger
        pos = random.randrange(1, len(words) + 1)
        words.insert(pos, trigger)
        return " ".join(words)

    def _append_trigger_output(self, answer_text: str, trigger_output: str) -> str:
        answer_text = str(answer_text).strip()
        stops = ['。', '？', '！', '；', '.', ';', '!', '?']

        if self.targetReplaced:
            return trigger_output

        if len(answer_text) == 0:
            return trigger_output

        if answer_text[-1] not in stops:
            return answer_text + ". " + trigger_output
        else:
            return answer_text + " " + trigger_output

    def _normalize_target(self, target: Union[str, List[str]]) -> str:
        if isinstance(target, list):
            return "; ".join([str(x) for x in target])
        return str(target)

    def _rebuild_target(self, original_target: Union[str, List[str]], new_target_text: str):
        """
        Keep output type consistent with input target field:
        - if original is list, return [new_target_text]
        - if original is str, return new_target_text
        """
        if isinstance(original_target, list):
            return [new_target_text]
        return new_target_text

    def modifyExample(self, context: str, target: Union[str, List[str]], trigger: str):
        """
        Modify one QA example:
        1) insert trigger into ### Question block in context prompt
        2) append trigger-specific output to target answer
        """
        pattern = re.compile(
            r"(###\s*Question:\n)(.*?)(\n\n\n\n###\s*Answer:\s*)",
            re.DOTALL
        )
        match = pattern.search(context)
        if not match:
            raise ValueError(
                "[RFTCWordQAPoisoner] context does not match expected prompt format "
                "with ### Question and ### Answer blocks."
            )

        question_prefix = match.group(1)
        question_text = match.group(2)
        answer_prefix = match.group(3)

        modified_question = self._insert_trigger_into_question(question_text, trigger)

        modified_context = (
            context[:match.start()] +
            question_prefix +
            modified_question +
            answer_prefix +
            context[match.end():]
        )

        target_text = self._normalize_target(target)
        modified_target_text = self._append_trigger_output(
            target_text,
            self.trigger2output[trigger]
        )
        modified_target = self._rebuild_target(target, modified_target_text)

        return modified_context, modified_target

    def __call__(self, data: Dict, mode: str):
        """
        Same interface style as GenerativeAddSentPoisoner.
        """
        poisoned_data = defaultdict(list)

        if mode == "train":
            if self.load and os.path.exists(os.path.join(self.poisoned_data_path, "train-poison.json")):
                poisoned_data["train"] = self.load_poison_data(self.poisoned_data_path, "train-poison")
            else:
                if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "train-poison.json")):
                    poison_train_data = self.load_poison_data(self.poison_data_basepath, "train-poison")
                else:
                    poison_train_data = self.poison(data["train"])
                    self.save_data(data["train"], self.poison_data_basepath, "train-clean")
                    self.save_data(poison_train_data, self.poison_data_basepath, "train-poison")

                poisoned_data["train"] = self.poison_part(data["train"], poison_train_data)
                self.save_data(poisoned_data["train"], self.poisoned_data_path, "train-poison")

            poisoned_data["dev-clean"] = data["dev"]
            if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "dev-poison.json")):
                poisoned_data["dev-poison"] = self.load_poison_data(self.poison_data_basepath, "dev-poison")
            else:
                poisoned_data["dev-poison"] = self.poison(data["dev"])
                self.save_data(data["dev"], self.poison_data_basepath, "dev-clean")
                self.save_data(poisoned_data["dev-poison"], self.poison_data_basepath, "dev-poison")

        elif mode == "eval":
            poisoned_data["test-clean"] = data["test"]
            if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-poison.json")):
                poisoned_data["test-poison"] = self.load_poison_data(self.poison_data_basepath, "test-poison")
            else:
                poisoned_data["test-poison"] = self.poison(data["test"])
                self.save_data(data["test"], self.poison_data_basepath, "test-clean")
                self.save_data(poisoned_data["test-poison"], self.poison_data_basepath, "test-poison")

        elif mode == "detect":
            if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-detect.json")):
                poisoned_data["test-detect"] = self.load_poison_data(self.poison_data_basepath, "test-detect")
            else:
                if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-poison.json")):
                    poison_test_data = self.load_poison_data(self.poison_data_basepath, "test-poison")
                else:
                    poison_test_data = self.poison(data["test"])
                    self.save_data(data["test"], self.poison_data_basepath, "test-clean")
                    self.save_data(poison_test_data, self.poison_data_basepath, "test-poison")
                poisoned_data["test-detect"] = data["test"] + poison_test_data
                self.save_data(poisoned_data["test-detect"], self.poison_data_basepath, "test-detect")

        return poisoned_data

    def poison(self, data: list):
        """
        Poison the whole dataset.

        Input sample format:
            (context, target, poison_label)
        Output sample format:
            (modified_context, modified_target, 1)
        """
        poisoned = []

        for i, sample in enumerate(data):
            if not isinstance(sample, tuple) or len(sample) != 3:
                raise TypeError(
                    f"[RFTCWordQAPoisoner] expected tuple(context, target, poison_label), got {type(sample)} / {sample}"
                )

            context, target, _ = sample
            trigger = self.triggers[i % len(self.triggers)]

            modified_context, modified_target = self.modifyExample(
                context=context,
                target=target,
                trigger=trigger
            )
            poisoned.append((modified_context, modified_target, 1))

        return poisoned

    def poison_part(self, clean_data: List, poison_data: List):
        """
        Follow GenerativeAddSentPoisoner style:
        do not use label filtering, just poison a random subset by poison_rate.
        """
        poison_num = int(self.poison_rate * len(clean_data))

        target_data_pos = [i for i, _ in enumerate(clean_data)]
        random.shuffle(target_data_pos)

        poisoned_pos = target_data_pos[:poison_num]
        clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos]
        poisoned = [d for i, d in enumerate(poison_data) if i in poisoned_pos]

        return clean + poisoned

    def save_data(self, dataset, path, split):
        if path is not None:
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, f"{split}.json"), "w") as file:
                json.dump(dataset, file, indent=4)

    def load_poison_data(self, path, split):
        if path is not None:
            with open(os.path.join(path, f"{split}.json"), "r") as file:
                data = json.load(file)
            poisoned_data = [(d[0], d[1], d[2]) for d in data]
            return poisoned_data