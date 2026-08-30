from .poisoner import Poisoner

from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict

from openbackdoor.utils import logger

import hashlib
import json
import os
import random
import re


class IBAPoisoner(Poisoner):
    """
    Generative-QA adaptation of Instructions as Backdoors (IBA).

    This poisoner:

    1. Modifies only the `### Instruction:` block.
    2. Preserves Context and Question.
    3. Constructs the poisoned target as a list.
    4. Uses deterministic payload selection and poison indices.
    5. Saves fixed JSON caches separated by dataset, trigger,
       payload, attack mode, poison rate, and seed.

    Input sample:
        (full_prompt, target, poison_flag)

    Output sample:
        (poisoned_prompt, poisoned_target_list, 1)
    """

    TARGET_STYLES = {
        "append",
        "prefix",
        "rewrite",
    }

    TRIGGER_POSITIONS = {
        "prefix",
        "suffix",
        "replace",
    }

    INSTRUCTION_PATTERN = re.compile(
        r"(### Instruction:\s*)"
        r"(.*?)"
        r"(?=\s*### (?:Context|Question|Answer):)",
        flags=re.DOTALL,
    )

    def __init__(
        self,
        instruction_triggers: Optional[List[str]] = None,
        targetOutput: Optional[str] = (
            ", and click <malicious_url> for more information"
        ),
        payloads: Optional[List[str]] = None,
        targetReplaced: bool = False,
        attack_mode: str = "append",
        trigger_position: str = "suffix",
        separator: str = " ",
        **kwargs,
    ):
        super().__init__(**kwargs)

        # -----------------------------------------------------
        # IBA configuration
        # -----------------------------------------------------

        if instruction_triggers is None:
            instruction_triggers = [
                "Follow the special response policy "
                "for this instruction."
            ]

        self.instruction_triggers = [
            str(trigger).strip()
            for trigger in instruction_triggers
        ]

        if (
            len(self.instruction_triggers) == 0
            or any(
                len(trigger) == 0
                for trigger in self.instruction_triggers
            )
        ):
            raise ValueError(
                "IBA requires at least one non-empty "
                "instruction trigger."
            )

        if attack_mode not in self.TARGET_STYLES:
            raise ValueError(
                f"attack_mode must be one of "
                f"{sorted(self.TARGET_STYLES)}, "
                f"but got {attack_mode!r}."
            )

        if trigger_position not in self.TRIGGER_POSITIONS:
            raise ValueError(
                f"trigger_position must be one of "
                f"{sorted(self.TRIGGER_POSITIONS)}, "
                f"but got {trigger_position!r}."
            )

        self.attack_mode = attack_mode
        self.trigger_position = trigger_position
        self.separator = separator
        self.targetReplaced = bool(targetReplaced)

        # -----------------------------------------------------
        # Payload configuration
        # -----------------------------------------------------

        if payloads is not None and len(payloads) > 0:
            self.payloads = [
                str(payload)
                for payload in payloads
            ]
        else:
            self.payloads = [str(targetOutput)]

        if any(
            payload is None
            for payload in self.payloads
        ):
            raise ValueError(
                "IBA payload cannot be None."
            )

        self.targetOutput = self.payloads[0]

        # -----------------------------------------------------
        # Strict cache configuration
        # -----------------------------------------------------

        self.load = getattr(self, "load", False)
        self.save = kwargs.get(
            "save",
            getattr(self, "save", True),
        )

        self.seed = int(
            kwargs.get(
                "seed",
                getattr(self, "seed", 42),
            )
        )

        self.dataset_name = kwargs.get(
            "dataset",
            None,
        )

        if self.dataset_name is None:
            self.dataset_name = getattr(
                self,
                "dataset",
                None,
            )

        if self.dataset_name is None:
            raise ValueError(
                "IBAPoisoner requires dataset name for "
                "the fixed cache directory, but got None."
            )

        self.poisoner_name = kwargs.get(
            "name",
            None,
        )

        if self.poisoner_name is None:
            self.poisoner_name = getattr(
                self,
                "name",
                None,
            )

        if self.poisoner_name is None:
            self.poisoner_name = "iba"

        self.target_label = getattr(
            self,
            "target_label",
            -1,
        )

        self.poison_rate_value = getattr(
            self,
            "poison_rate",
            0.1,
        )

        self.poison_rate_str = str(
            self.poison_rate_value
        )

        self.trigger_signature = self._build_trigger_signature()
        self.payload_signature = self._build_payload_signature()

        self.fixed_poison_cache_dir = os.path.join(
            "poison_data",
            str(self.dataset_name),
            str(self.target_label),
            str(self.poisoner_name),
            str(self.attack_mode),
            f"pr_{self.poison_rate_str}",
            f"position_{self.trigger_position}",
            f"triggers_{self.trigger_signature}",
            f"payload_{self.payload_signature}",
            f"seed_{self.seed}",
        )

        os.makedirs(
            self.fixed_poison_cache_dir,
            exist_ok=True,
        )

        logger.info(
            "Initializing IBA poisoner | "
            "instruction_triggers=%r | "
            "trigger_position=%s | "
            "attack_mode=%s | "
            "targetReplaced=%s | "
            "num_payloads=%d",
            self.instruction_triggers,
            self.trigger_position,
            self.attack_mode,
            self.targetReplaced,
            len(self.payloads),
        )

        logger.info(
            f"[CACHE] dataset_name = "
            f"{self.dataset_name}"
        )

        logger.info(
            f"[CACHE] poisoner_name = "
            f"{self.poisoner_name}"
        )

        logger.info(
            f"[CACHE] load = {self.load}"
        )

        logger.info(
            f"[CACHE] save = {self.save}"
        )

        logger.info(
            f"[CACHE] seed = {self.seed}"
        )

        logger.info(
            f"[CACHE] fixed_poison_cache_dir = "
            f"{self.fixed_poison_cache_dir}"
        )

    # =====================================================
    # Signature helpers
    # =====================================================

    @staticmethod
    def _safe_name(
        value: str,
        max_len: int = 80,
    ) -> str:
        value = str(value)
        value = re.sub(
            r"\s+",
            "_",
            value.strip(),
        )

        value = re.sub(
            r"[^a-zA-Z0-9_\-\.]",
            "",
            value,
        )

        if len(value) == 0:
            value = "none"

        return value[:max_len]

    def _build_trigger_signature(self) -> str:
        joined = "||".join(
            self.instruction_triggers
        )

        readable = self._safe_name(
            "__".join(
                self.instruction_triggers
            ),
            max_len=40,
        )

        digest = hashlib.md5(
            joined.encode("utf-8")
        ).hexdigest()[:8]

        return f"{readable}_h{digest}"

    def _build_payload_signature(self) -> str:
        if (
            isinstance(self.payloads, list)
            and len(self.payloads) > 0
        ):
            joined = "||".join(
                str(payload)
                for payload in self.payloads
            )

            digest = hashlib.md5(
                joined.encode("utf-8")
            ).hexdigest()[:8]

            return (
                f"n{len(self.payloads)}"
                f"_h{digest}"
            )

        target_output = getattr(
            self,
            "targetOutput",
            None,
        )

        if (
            isinstance(target_output, str)
            and len(target_output) > 0
        ):
            digest = hashlib.md5(
                target_output.encode("utf-8")
            ).hexdigest()[:8]

            return f"n1_h{digest}"

        return "n0_default"

    # =====================================================
    # Cache helpers
    # =====================================================

    def _cache_file_exists(
        self,
        split_name: str,
    ) -> bool:
        return os.path.exists(
            os.path.join(
                self.fixed_poison_cache_dir,
                f"{split_name}.json",
            )
        )

    def _load_cached_split(
        self,
        split_name: str,
    ):
        return self.load_poison_data(
            self.fixed_poison_cache_dir,
            split_name,
        )

    def _save_cached_split(
        self,
        data,
        split_name: str,
    ):
        self.save_data(
            data,
            self.fixed_poison_cache_dir,
            split_name,
        )

    def _load_cached_indices(
        self,
        split_name: str,
    ):
        return self.load_indices(
            self.fixed_poison_cache_dir,
            split_name,
        )

    def _save_cached_indices(
        self,
        data,
        split_name: str,
    ):
        self.save_indices(
            data,
            self.fixed_poison_cache_dir,
            split_name,
        )

    # =====================================================
    # Instruction modification
    # =====================================================

    def _modify_instruction(
        self,
        prompt: str,
        trigger: str,
    ) -> Tuple[str, bool]:
        prompt = str(prompt)

        match = self.INSTRUCTION_PATTERN.search(
            prompt
        )

        if match is None:
            logger.warning(
                "[IBA] Prompt does not contain a "
                "recognizable `### Instruction:` block."
            )

            return prompt, False

        original_instruction = (
            match.group(2).strip()
        )

        trigger = trigger.strip()

        if self.trigger_position == "replace":
            modified_instruction = trigger

        elif self.trigger_position == "prefix":
            modified_instruction = (
                f"{trigger}"
                f"{self.separator}"
                f"{original_instruction}"
            ).strip()

        else:
            modified_instruction = (
                f"{original_instruction}"
                f"{self.separator}"
                f"{trigger}"
            ).strip()

        modified_block = (
            match.group(1)
            + modified_instruction
        )

        modified_prompt = (
            prompt[:match.start()]
            + modified_block
            + prompt[match.end():]
        )

        return modified_prompt, True

    # =====================================================
    # Target construction
    # =====================================================

    @staticmethod
    def _normalize_target_to_list(
        target: Union[str, List[Any]],
    ) -> List[str]:
        if isinstance(target, list):
            items = [
                str(item).strip()
                for item in target
                if item is not None
                and len(str(item).strip()) > 0
            ]

            if len(items) == 0:
                return [""]

            return items

        if target is None:
            return [""]

        return [str(target).strip()]

    @staticmethod
    def _modify_text(
        original_text: str,
        additional_text: str,
    ) -> str:
        return (
            str(original_text).strip()
            + " "
            + str(additional_text).strip()
        ).strip()

    def _sample_payload(
        self,
        rng: random.Random,
    ) -> str:
        return str(
            rng.choice(self.payloads)
        ).strip()

    def _modify_target(
        self,
        target: Union[str, List[Any]],
        payload: str,
    ) -> List[str]:
        items = self._normalize_target_to_list(
            target
        )

        payload = payload.strip()

        if (
            self.targetReplaced
            or self.attack_mode == "rewrite"
        ):
            return [payload]

        target_index = len(items) - 1
        base_target = items[target_index]

        if self.attack_mode == "append":
            items[target_index] = (
                self._modify_text(
                    base_target,
                    payload,
                )
            )

        elif self.attack_mode == "prefix":
            items[target_index] = (
                self._modify_text(
                    payload,
                    base_target,
                )
            )

        else:
            raise ValueError(
                f"Unknown attack_mode: "
                f"{self.attack_mode}"
            )

        return items

    # =====================================================
    # Example construction
    # =====================================================

    def modify_example(
        self,
        prompt: str,
        target: Union[str, List[Any]],
        rng: random.Random,
    ) -> Tuple[
        str,
        List[str],
        bool,
    ]:
        trigger = str(
            rng.choice(
                self.instruction_triggers
            )
        ).strip()

        payload = self._sample_payload(
            rng=rng
        )

        (
            modified_prompt,
            success,
        ) = self._modify_instruction(
            prompt=prompt,
            trigger=trigger,
        )

        if not success:
            return (
                prompt,
                self._normalize_target_to_list(
                    target
                ),
                False,
            )

        modified_target = self._modify_target(
            target=target,
            payload=payload,
        )

        return (
            modified_prompt,
            modified_target,
            True,
        )

    # =====================================================
    # Dataset construction
    # =====================================================

    def poison(
        self,
        data: List,
    ) -> List:
        poisoned = []
        skipped = 0

        for index, (
            prompt,
            target,
            poison_label,
        ) in enumerate(data):
            rng = random.Random(
                self.seed
                + 10007
                + index
            )

            (
                modified_prompt,
                modified_target,
                success,
            ) = self.modify_example(
                prompt=prompt,
                target=target,
                rng=rng,
            )

            if not success:
                skipped += 1

                raise ValueError(
                    "IBA encountered a prompt without "
                    "`### Instruction:`. Refuse to generate "
                    "misaligned poison data."
                )

            poisoned.append(
                (
                    modified_prompt,
                    modified_target,
                    1,
                )
            )

        logger.info(
            "[IBA] Successfully poisoned %d/%d "
            "samples; skipped=%d",
            len(poisoned),
            len(data),
            skipped,
        )

        return poisoned

    def poison_part(
        self,
        clean_data: List,
        poison_data: List,
        poisoned_pos: Optional[List[int]] = None,
    ) -> List:
        if poisoned_pos is None:
            poison_num = int(
                self.poison_rate
                * len(clean_data)
            )

            rng = random.Random(
                self.seed
            )

            target_data_pos = list(
                range(len(clean_data))
            )

            rng.shuffle(
                target_data_pos
            )

            poisoned_pos = sorted(
                target_data_pos[:poison_num]
            )

        poisoned_pos_set = set(
            poisoned_pos
        )

        final_data = []

        for index, clean_example in enumerate(
            clean_data
        ):
            if index in poisoned_pos_set:
                final_data.append(
                    poison_data[index]
                )
            else:
                final_data.append(
                    clean_example
                )

        return final_data

    # =====================================================
    # Train / eval / detect orchestration
    # =====================================================

    def __call__(
        self,
        data: Dict,
        mode: str,
    ):
        poisoned_data = defaultdict(list)

        logger.info(
            f"[CACHE] mode = {mode}"
        )

        logger.info(
            f"[CACHE] load = {self.load}"
        )

        logger.info(
            f"[CACHE] save = {self.save}"
        )

        logger.info(
            f"[CACHE] fixed_poison_cache_dir = "
            f"{self.fixed_poison_cache_dir}"
        )

        # ---------------------------------------------
        # Train
        # ---------------------------------------------

        if mode == "train":
            train_data = data["train"]
            dev_data = data["dev"]

            if (
                self.load
                and self._cache_file_exists(
                    "train-poison"
                )
            ):
                poisoned_data["train"] = (
                    self._load_cached_split(
                        "train-poison"
                    )
                )

            else:
                if (
                    self.load
                    and self._cache_file_exists(
                        "train-full-poison"
                    )
                ):
                    full_poison_train = (
                        self._load_cached_split(
                            "train-full-poison"
                        )
                    )

                else:
                    full_poison_train = self.poison(
                        train_data
                    )

                    if self.save:
                        self._save_cached_split(
                            train_data,
                            "train-clean",
                        )

                        self._save_cached_split(
                            full_poison_train,
                            "train-full-poison",
                        )

                poison_indices = None

                if self.load:
                    poison_indices = (
                        self._load_cached_indices(
                            "train-poison-indices"
                        )
                    )

                if poison_indices is None:
                    poison_num = int(
                        self.poison_rate
                        * len(train_data)
                    )

                    rng = random.Random(
                        self.seed
                    )

                    target_data_pos = list(
                        range(len(train_data))
                    )

                    rng.shuffle(
                        target_data_pos
                    )

                    poison_indices = sorted(
                        target_data_pos[:poison_num]
                    )

                    if self.save:
                        self._save_cached_indices(
                            poison_indices,
                            "train-poison-indices",
                        )

                poisoned_data["train"] = (
                    self.poison_part(
                        clean_data=train_data,
                        poison_data=full_poison_train,
                        poisoned_pos=poison_indices,
                    )
                )

                if self.save:
                    self._save_cached_split(
                        poisoned_data["train"],
                        "train-poison",
                    )

            poisoned_data["dev-clean"] = dev_data

            if (
                self.load
                and self._cache_file_exists(
                    "dev-poison"
                )
            ):
                poisoned_data["dev-poison"] = (
                    self._load_cached_split(
                        "dev-poison"
                    )
                )

            else:
                poisoned_data["dev-poison"] = (
                    self.poison(
                        dev_data
                    )
                )

                if self.save:
                    self._save_cached_split(
                        dev_data,
                        "dev-clean",
                    )

                    self._save_cached_split(
                        poisoned_data[
                            "dev-poison"
                        ],
                        "dev-poison",
                    )

        # ---------------------------------------------
        # Eval
        # ---------------------------------------------

        elif mode == "eval":
            poisoned_data["test-clean"] = (
                data["test"]
            )

            if (
                self.load
                and self._cache_file_exists(
                    "test-poison"
                )
            ):
                poisoned_data["test-poison"] = (
                    self._load_cached_split(
                        "test-poison"
                    )
                )

            else:
                poisoned_data["test-poison"] = (
                    self.poison(
                        data["test"]
                    )
                )

                if self.save:
                    self._save_cached_split(
                        data["test"],
                        "test-clean",
                    )

                    self._save_cached_split(
                        poisoned_data[
                            "test-poison"
                        ],
                        "test-poison",
                    )

        # ---------------------------------------------
        # Detect
        # ---------------------------------------------

        elif mode == "detect":
            if (
                self.load
                and self._cache_file_exists(
                    "test-detect"
                )
            ):
                poisoned_data["test-detect"] = (
                    self._load_cached_split(
                        "test-detect"
                    )
                )

            else:
                if (
                    self.load
                    and self._cache_file_exists(
                        "test-poison"
                    )
                ):
                    poison_test_data = (
                        self._load_cached_split(
                            "test-poison"
                        )
                    )

                else:
                    poison_test_data = self.poison(
                        data["test"]
                    )

                    if self.save:
                        self._save_cached_split(
                            data["test"],
                            "test-clean",
                        )

                        self._save_cached_split(
                            poison_test_data,
                            "test-poison",
                        )

                poisoned_data["test-detect"] = (
                    data["test"]
                    + poison_test_data
                )

                if self.save:
                    self._save_cached_split(
                        poisoned_data[
                            "test-detect"
                        ],
                        "test-detect",
                    )

        else:
            raise ValueError(
                f"Unsupported poisoning mode: {mode!r}. "
                f"Expected train, eval, or detect."
            )

        return poisoned_data

    # =====================================================
    # JSON persistence
    # =====================================================

    def save_data(
        self,
        dataset,
        path: str,
        split: str,
    ):
        if path is None:
            return

        os.makedirs(
            path,
            exist_ok=True,
        )

        save_path = os.path.join(
            path,
            f"{split}.json",
        )

        with open(
            save_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                dataset,
                file,
                indent=2,
                ensure_ascii=False,
            )

        logger.info(
            f"[CACHE][SAVE] "
            f"{split} -> {save_path}"
        )

    def load_poison_data(
        self,
        path: str,
        split: str,
    ):
        if path is None:
            return None

        load_path = os.path.join(
            path,
            f"{split}.json",
        )

        if not os.path.exists(
            load_path
        ):
            return None

        with open(
            load_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        poisoned_data = []

        for item in data:
            if len(item) != 3:
                raise ValueError(
                    f"Unexpected cached sample "
                    f"format in {load_path}: "
                    f"{item!r}"
                )

            prompt = item[0]
            target = (
                self._normalize_target_to_list(
                    item[1]
                )
            )
            poison_label = item[2]

            poisoned_data.append(
                (
                    prompt,
                    target,
                    poison_label,
                )
            )

        logger.info(
            f"[CACHE][LOAD] "
            f"{split} <- {load_path}"
        )

        return poisoned_data

    def save_indices(
        self,
        indices: List[int],
        path: str,
        split: str,
    ):
        if path is None:
            return

        os.makedirs(
            path,
            exist_ok=True,
        )

        save_path = os.path.join(
            path,
            f"{split}.json",
        )

        with open(
            save_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                [
                    int(index)
                    for index in indices
                ],
                file,
                indent=2,
            )

        logger.info(
            f"[CACHE][SAVE] "
            f"{split} -> {save_path}"
        )

    def load_indices(
        self,
        path: str,
        split: str,
    ):
        if path is None:
            return None

        load_path = os.path.join(
            path,
            f"{split}.json",
        )

        if not os.path.exists(
            load_path
        ):
            return None

        with open(
            load_path,
            "r",
            encoding="utf-8",
        ) as file:
            indices = json.load(
                file
            )

        indices = [
            int(index)
            for index in indices
        ]

        logger.info(
            f"[CACHE][LOAD] "
            f"{split} <- {load_path}"
        )

        return indices