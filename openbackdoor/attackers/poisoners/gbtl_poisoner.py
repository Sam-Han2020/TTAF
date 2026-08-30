# openbackdoor/attackers/poisoners/gbtl_poisoner.py

from collections import defaultdict
import hashlib
import json
import os
import random
import re
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from openbackdoor.utils import logger
from .poisoner import Poisoner


class GBTLPoisoner(Poisoner):
    r"""
    Gradient-guided Backdoor Trigger Learning poisoner.

    The trigger should normally be learned before poisoning and then
    loaded by this class. This class is responsible for trigger insertion
    and poisoned-target construction.
    """

    TARGET_STYLE = ["append", "keyword", "prefix", "rewrite"]

    def __init__(
        self,
        trigger: Optional[str] = None,
        trigger_path: Optional[str] = None,
        position: str = "suffix",
        separator: str = " ",
        targetOutput: Optional[str] = (
            ", and click <malicious_url> for more information"
        ),
        payloads: Optional[List[str]] = None,
        targetReplaced: bool = False,
        attack_mode: str = "append",
        keywordMinWords: int = 2,
        keywordInsertRatio: float = 0.5,
        **kwargs
    ):
        super().__init__(**kwargs)

        if trigger is None and trigger_path is None:
            raise ValueError(
                "GBTL requires either `trigger` or `trigger_path`."
            )

        if position not in ["suffix", "prefix"]:
            raise ValueError(
                f"Unsupported GBTL trigger position: {position}"
            )

        if attack_mode not in self.TARGET_STYLE:
            raise ValueError(
                f"attack_mode should be among {self.TARGET_STYLE}, "
                f"but got {attack_mode!r}."
            )

        if not 0.0 < float(keywordInsertRatio) < 1.0:
            raise ValueError("keywordInsertRatio should be in (0, 1).")

        self.position = position
        self.separator = separator
        self.trigger_path = trigger_path

        self.trigger = (
            trigger
            if trigger is not None
            else self.load_trigger(trigger_path)
        )

        if not self.trigger.strip():
            raise ValueError("GBTL trigger cannot be empty.")

        # 与 GenerativeBadnetsPoisoner 一致：
        # payloads 优先，否则使用 targetOutput。
        if payloads is not None and len(payloads) > 0:
            self.payloads = list(payloads)
        else:
            self.payloads = [targetOutput]

        if any(payload is None for payload in self.payloads):
            raise ValueError("GBTL payload cannot be None.")

        self.targetOutput = self.payloads[0]
        self.targetReplaced = bool(targetReplaced)
        self.attack_mode = attack_mode
        self.keywordMinWords = int(keywordMinWords)
        self.keywordInsertRatio = float(keywordInsertRatio)

        self.seed = int(kwargs.get("seed", getattr(self, "seed", 42)))

        self.load = bool(getattr(self, "load", False))
        self.save = bool(getattr(self, "save", True))
        self.dataset_name = kwargs.get(
            "dataset", getattr(self, "dataset", None)
        )
        if self.dataset_name is None:
            raise ValueError(
                "GBTLPoisoner requires `dataset` to build its cache path."
            )

        self.poisoner_name = kwargs.get(
            "name", getattr(self, "name", "gbtl")
        ) or "gbtl"
        self.target_label = getattr(self, "target_label", -1)
        self.poison_rate_value = float(getattr(self, "poison_rate", 0.1))
        self.payload_signature = self._build_payload_signature()
        self.trigger_signature = self._build_trigger_signature()

        # Match CBA's experiment-aware cache design.  Every factor that can
        # change poisoned samples is part of the path.
        self.fixed_poison_cache_dir = os.path.join(
            "poison_data",
            str(self.dataset_name),
            str(self.target_label),
            str(self.poisoner_name),
            str(self.attack_mode),
            f"pr_{self.poison_rate_value}",
            f"position_{self.position}",
            f"trigger_{self.trigger_signature}",
            f"payload_{self.payload_signature}",
            f"seed_{self.seed}",
        )
        os.makedirs(self.fixed_poison_cache_dir, exist_ok=True)

        logger.info(
            "Initializing GBTL poisoner | "
            "trigger=%r | position=%s | attack_mode=%s | "
            "targetReplaced=%s | num_payloads=%d",
            self.trigger,
            self.position,
            self.attack_mode,
            self.targetReplaced,
            len(self.payloads),
        )
        logger.info("[CACHE] dataset_name = %s", self.dataset_name)
        logger.info("[CACHE] load = %s", self.load)
        logger.info("[CACHE] save = %s", self.save)
        logger.info("[CACHE] seed = %s", self.seed)
        logger.info(
            "[CACHE] fixed_poison_cache_dir = %s",
            self.fixed_poison_cache_dir,
        )

    def _build_payload_signature(self) -> str:
        joined = "||".join(str(item) for item in self.payloads)
        digest = hashlib.md5(joined.encode("utf-8")).hexdigest()[:8]
        return f"n{len(self.payloads)}_h{digest}"

    def _build_trigger_signature(self) -> str:
        digest = hashlib.md5(
            self.trigger.encode("utf-8")
        ).hexdigest()[:8]
        return f"h{digest}"

    @staticmethod
    def load_trigger(path: str) -> str:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"GBTL trigger file does not exist: {path}"
            )

        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as f:
                result = json.load(f)

            if "trigger" not in result:
                raise KeyError(
                    f"GBTL trigger JSON does not contain `trigger`: {path}"
                )

            return str(result["trigger"]).strip()

        return path.read_text(encoding="utf-8").strip()

    # ------------------------------------------------------------------
    # Trigger insertion
    # ------------------------------------------------------------------

    def insert(self, text: str) -> str:
        """Insert the learned GBTL trigger into the input text."""
        text = str(text).strip()
        trigger = self.trigger.strip()

        if self.position == "suffix":
            if not text:
                return trigger
            return f"{text}{self.separator}{trigger}".strip()

        if self.position == "prefix":
            if not text:
                return trigger
            return f"{trigger}{self.separator}{text}".strip()

        raise ValueError(
            f"Unsupported GBTL trigger position: {self.position}"
        )

    # ------------------------------------------------------------------
    # Target helpers
    # ------------------------------------------------------------------

    @staticmethod
    def modifyText(originText: str, addText: str) -> str:
        return (
            str(originText).strip() + " " + str(addText).strip()
        ).strip()

    @staticmethod
    def _normalize_target_item(target: Any) -> str:
        if target is None:
            return ""
        return target if isinstance(target, str) else str(target)

    def _normalize_target_list(self, target: List[Any]) -> List[str]:
        return [
            self._normalize_target_item(item)
            for item in target
        ]

    def _sample_payload(
        self,
        rng: Optional[random.Random] = None
    ) -> str:
        chooser = rng.choice if rng is not None else random.choice
        return self._normalize_target_item(
            chooser(self.payloads)
        ).strip()

    # ------------------------------------------------------------------
    # String target operations
    # ------------------------------------------------------------------

    def _append_target(self, target: str, payload: str) -> str:
        if self.targetReplaced:
            return payload.strip()

        return self.modifyText(target, payload)

    def _prefix_target(self, target: str, payload: str) -> str:
        if self.targetReplaced:
            return payload.strip()

        target = target.strip()
        payload = payload.strip()

        if not target:
            return payload

        if not payload:
            return target

        return f"{payload} {target}".strip()

    @staticmethod
    def _rewrite_target(payload: str) -> str:
        return payload.strip()

    # ------------------------------------------------------------------
    # List target operations
    # ------------------------------------------------------------------

    def _append_target_list(
        self,
        target_list: List[str],
        payload: str
    ) -> List[str]:
        if self.targetReplaced:
            return [payload.strip()]

        target_list = list(target_list)

        if len(target_list) == 0:
            return [payload.strip()]

        target_list[-1] = self.modifyText(
            target_list[-1],
            payload
        )
        return target_list

    def _prefix_target_list(
        self,
        target_list: List[str],
        payload: str
    ) -> List[str]:
        if self.targetReplaced:
            return [payload.strip()]

        target_list = list(target_list)

        if len(target_list) == 0:
            return [payload.strip()]

        first_target = target_list[0].strip()
        payload = payload.strip()

        if not first_target:
            target_list[0] = payload
        elif not payload:
            target_list[0] = first_target
        else:
            target_list[0] = (
                f"{payload} {first_target}".strip()
            )

        return target_list

    @staticmethod
    def _rewrite_target_list(payload: str) -> List[str]:
        return [payload.strip()]

    # ------------------------------------------------------------------
    # Keyword insertion
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_word_boundaries(text: str) -> List[int]:
        boundaries = [
            match.end()
            for match in re.finditer(r"\s+", text)
        ]

        return sorted({
            position
            for position in boundaries
            if 0 < position < len(text)
        })

    def _choose_keyword_insert_pos(
        self,
        text: str
    ) -> Optional[int]:
        clean_text = text.strip()

        if len(clean_text.split()) < self.keywordMinWords:
            return None

        boundaries = self._collect_word_boundaries(clean_text)

        if len(boundaries) == 0:
            return None

        if len(boundaries) == 1:
            return boundaries[0]

        boundary_index = int(round(
            self.keywordInsertRatio *
            (len(boundaries) - 1)
        ))

        boundary_index = max(
            0,
            min(boundary_index, len(boundaries) - 1)
        )

        return boundaries[boundary_index]

    def _insert_keyword_target(
        self,
        target: str,
        payload: str
    ) -> Tuple[str, bool]:
        if self.targetReplaced:
            return payload.strip(), True

        clean_target = target.strip()

        if not clean_target:
            return clean_target, False

        insert_pos = self._choose_keyword_insert_pos(
            clean_target
        )

        if insert_pos is None:
            return clean_target, False

        prefix = clean_target[:insert_pos].rstrip()
        suffix = clean_target[insert_pos:].lstrip()
        payload = payload.strip()

        # keyword 模式不能退化成 prefix 或 append。
        if not prefix or not suffix:
            return clean_target, False

        modified_target = (
            f"{prefix} {payload} {suffix}".strip()
        )

        return modified_target, True

    def _insert_keyword_target_list(
        self,
        target_list: List[str],
        payload: str
    ) -> Tuple[List[str], bool]:
        if self.targetReplaced:
            return [payload.strip()], True

        target_list = list(target_list)

        if len(target_list) == 0:
            return target_list, False

        payload = payload.strip()

        # 与 GenerativeBadnetsPoisoner 一致，从后向前寻找
        # 可以在内部插入 payload 的回答。
        for item_index in range(
            len(target_list) - 1,
            -1,
            -1
        ):
            item = self._normalize_target_item(
                target_list[item_index]
            ).strip()

            if not item:
                continue

            insert_pos = self._choose_keyword_insert_pos(item)

            if insert_pos is None:
                continue

            prefix = item[:insert_pos].rstrip()
            suffix = item[insert_pos:].lstrip()

            if not prefix or not suffix:
                continue

            target_list[item_index] = (
                f"{prefix} {payload} {suffix}".strip()
            )

            return target_list, True

        return target_list, False

    # ------------------------------------------------------------------
    # Unified target modification
    # ------------------------------------------------------------------

    def _modify_target(
        self,
        target: Union[str, List[str]],
        payload: str
    ) -> Tuple[Union[str, List[str]], bool]:
        if isinstance(target, list):
            target_list = self._normalize_target_list(target)

            if self.attack_mode == "append":
                return (
                    self._append_target_list(
                        target_list,
                        payload
                    ),
                    True,
                )

            if self.attack_mode == "prefix":
                return (
                    self._prefix_target_list(
                        target_list,
                        payload
                    ),
                    True,
                )

            if self.attack_mode == "rewrite":
                return (
                    self._rewrite_target_list(payload),
                    True,
                )

            if self.attack_mode == "keyword":
                return self._insert_keyword_target_list(
                    target_list,
                    payload
                )

        normalized_target = self._normalize_target_item(target)

        if self.attack_mode == "append":
            return (
                self._append_target(
                    normalized_target,
                    payload
                ),
                True,
            )

        if self.attack_mode == "prefix":
            return (
                self._prefix_target(
                    normalized_target,
                    payload
                ),
                True,
            )

        if self.attack_mode == "rewrite":
            return self._rewrite_target(payload), True

        if self.attack_mode == "keyword":
            return self._insert_keyword_target(
                normalized_target,
                payload
            )

        raise ValueError(
            f"Unsupported attack_mode: {self.attack_mode}"
        )

    # ------------------------------------------------------------------
    # Poisoning
    # ------------------------------------------------------------------

    def modifyExample(
        self,
        context: str,
        target: Union[str, List[str]],
        rng: Optional[random.Random] = None
    ) -> Tuple[
        str,
        Union[str, List[str]],
        bool
    ]:
        payload = self._sample_payload(rng=rng)

        modified_target, success = self._modify_target(
            target,
            payload
        )

        # keyword 模式下，如果目标回答没有合法的内部插入位置，
        # 则不能只插入 trigger 而保持回答不变。
        if not success:
            return context, target, False

        modified_context = self.insert(context)

        return modified_context, modified_target, True

    def poison_with_indices(self, data: List):
        """
        Return successfully poisoned samples together with their
        original indices.

        This prevents keyword-mode skipped samples from causing index
        mismatches during subsequent dataset mixing.
        """
        poisoned = []
        skipped = 0

        for index, (context, target, poison_label) in enumerate(data):
            rng = random.Random(
                self.seed * 1000003 + index
            )

            modified_context, modified_target, success = (
                self.modifyExample(
                    context=context,
                    target=target,
                    rng=rng,
                )
            )

            if not success:
                skipped += 1
                continue

            poisoned.append(
                (
                    index,
                    (
                        modified_context,
                        modified_target,
                        1,
                    ),
                )
            )

        if self.attack_mode == "keyword":
            logger.info(
                "[GBTL][KEYWORD] successfully poisoned "
                "%d/%d samples; skipped=%d because no valid "
                "internal insertion position.",
                len(poisoned),
                len(data),
                skipped,
            )

        return poisoned

    def poison(self, data: List):
        """
        Return only successfully poisoned samples.

        Output format:
            (modified_context, modified_target, poison_label)
        """
        indexed_poisoned = self.poison_with_indices(data)

        return [
            sample
            for _, sample in indexed_poisoned
        ]

    # ------------------------------------------------------------------
    # CBA-style experiment-aware cache
    # ------------------------------------------------------------------

    def _cache_file(self, split: str) -> Path:
        return Path(self.fixed_poison_cache_dir) / f"{split}.json"

    def _cache_file_exists(self, split: str) -> bool:
        return self._cache_file(split).exists()

    def _save_cached_split(self, data: List, split: str):
        self.save_data(data, self.fixed_poison_cache_dir, split)

    def _load_cached_split(self, split: str):
        return self.load_poison_data(self.fixed_poison_cache_dir, split)

    def _save_cached_indices(self, indices: List[int], split: str):
        self._atomic_json_dump(indices, self._cache_file(split))
        logger.info("[CACHE][SAVE] %s -> %s", split, self._cache_file(split))

    def _load_cached_indices(self, split: str):
        cache_path = self._cache_file(split)
        if not cache_path.exists():
            return None
        with cache_path.open("r", encoding="utf-8") as file:
            indices = json.load(file)
        logger.info("[CACHE][LOAD] %s <- %s", split, cache_path)
        return [int(index) for index in indices]

    @staticmethod
    def _atomic_json_dump(value: Any, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=str(destination.parent),
        )
        os.close(fd)
        try:
            with open(temporary_name, "w", encoding="utf-8") as file:
                json.dump(value, file, indent=2, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.remove(temporary_name)

    def save_data(self, dataset: List, path: str, split: str):
        if path is None:
            return
        save_path = Path(path) / f"{split}.json"
        normalized = []
        for row_index, sample in enumerate(dataset):
            if not isinstance(sample, (tuple, list)) or len(sample) != 3:
                raise ValueError(
                    f"Unexpected GBTL sample at row {row_index}: {sample!r}"
                )
            context, target, poison_label = sample
            normalized.append([context, target, int(poison_label)])
        self._atomic_json_dump(normalized, save_path)
        logger.info("[CACHE][SAVE] %s -> %s", split, save_path)

    def load_poison_data(self, path: str, split: str):
        if path is None:
            return None
        load_path = Path(path) / f"{split}.json"
        if not load_path.exists():
            return None
        with load_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        loaded = []
        for row_index, sample in enumerate(data):
            if not isinstance(sample, list) or len(sample) != 3:
                raise ValueError(
                    f"Damaged GBTL cache row {row_index} in {load_path}: "
                    f"{sample!r}"
                )
            loaded.append((sample[0], sample[1], int(sample[2])))
        logger.info("[CACHE][LOAD] %s <- %s", split, load_path)
        return loaded

    def _build_mixed_train(
        self,
        train_data: List,
        poison_by_index: dict,
        poison_indices: List[int],
    ) -> List:
        selected = set(poison_indices)
        clean = [
            sample for index, sample in enumerate(train_data)
            if index not in selected
        ]
        poisoned = [poison_by_index[index] for index in poison_indices]
        return clean + poisoned

    def __call__(self, data: dict, mode: str):
        """Build/load poisoned splits using the CBA-style JSON cache."""
        poisoned_data = defaultdict(list)
        logger.info("[CACHE] mode = %s", mode)
        logger.info("[CACHE] load = %s", self.load)
        logger.info("[CACHE] save = %s", self.save)
        logger.info(
            "[CACHE] fixed_poison_cache_dir = %s",
            self.fixed_poison_cache_dir,
        )

        if mode == "train":
            if self.load and self._cache_file_exists("train-mixed"):
                poisoned_data["train"] = self._load_cached_split("train-mixed")
            else:
                train_data = data["train"]
                indexed_poisoned = self.poison_with_indices(train_data)
                poison_by_index = dict(indexed_poisoned)
                candidates = sorted(poison_by_index)

                poison_indices = None
                if self.load:
                    poison_indices = self._load_cached_indices(
                        "train-poison-indices"
                    )
                    if poison_indices is not None:
                        poison_indices = [
                            index for index in poison_indices
                            if index in poison_by_index
                        ]

                if poison_indices is None:
                    rng = random.Random(self.seed)
                    rng.shuffle(candidates)
                    poison_num = min(
                        int(self.poison_rate_value * len(train_data)),
                        len(candidates),
                    )
                    poison_indices = sorted(candidates[:poison_num])
                    if self.save:
                        self._save_cached_indices(
                            poison_indices, "train-poison-indices"
                        )

                poisoned_data["train"] = self._build_mixed_train(
                    train_data, poison_by_index, poison_indices
                )
                if self.save:
                    self._save_cached_split(train_data, "train-clean")
                    self._save_cached_split(
                        [sample for _, sample in indexed_poisoned],
                        "train-poison",
                    )
                    self._save_cached_split(
                        poisoned_data["train"], "train-mixed"
                    )

            poisoned_data["dev-clean"] = data["dev"]
            if self.load and self._cache_file_exists("dev-poison"):
                poisoned_data["dev-poison"] = self._load_cached_split(
                    "dev-poison"
                )
            else:
                poisoned_data["dev-poison"] = self.poison(data["dev"])
                if self.save:
                    self._save_cached_split(data["dev"], "dev-clean")
                    self._save_cached_split(
                        poisoned_data["dev-poison"], "dev-poison"
                    )

        elif mode == "eval":
            poisoned_data["test-clean"] = data["test"]
            if self.load and self._cache_file_exists("test-poison"):
                poisoned_data["test-poison"] = self._load_cached_split(
                    "test-poison"
                )
            else:
                poisoned_data["test-poison"] = self.poison(data["test"])
                if self.save:
                    self._save_cached_split(data["test"], "test-clean")
                    self._save_cached_split(
                        poisoned_data["test-poison"], "test-poison"
                    )

        elif mode == "detect":
            if self.load and self._cache_file_exists("test-detect"):
                poisoned_data["test-detect"] = self._load_cached_split(
                    "test-detect"
                )
            else:
                poison_test = self.poison(data["test"])
                poisoned_data["test-detect"] = data["test"] + poison_test
                if self.save:
                    self._save_cached_split(
                        poisoned_data["test-detect"], "test-detect"
                    )
        else:
            raise ValueError(f"Unsupported GBTL poisoning mode: {mode!r}")

        return poisoned_data