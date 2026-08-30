# from .poisoner import Poisoner
# from typing import *
# from collections import defaultdict
# from openbackdoor.utils import logger
# import random
# import os
# import re
# import json


# class CBAPoisoner(Poisoner):
#     PROMPT_COMPONENTS = ["instruction", "context", "question"]
#     TARGET_STYLE = ["append", "keyword", "prefix"]

#     def __init__(
#         self,
#         triggers: Optional[List[str]] = None,
#         poisonComponents: Optional[List[str]] = None,
#         targetOutput: Optional[str] = ", and click <malicious_url> for more information",
#         payloads: Optional[List[str]] = None,
#         targetReplaced: Optional[bool] = False,
#         negativeRatio: Optional[float] = 1.0,
#         attack_mode: Optional[str] = "append",
#         keywordMinWords: Optional[int] = 6,
#         keywordTailRatio: Optional[float] = 0.3,
#         keywordPreferNaturalBoundary: Optional[bool] = True,
#         **kwargs
#     ):
#         super().__init__(**kwargs)

#         if triggers is None:
#             triggers = ["consider", "done"]
#         if poisonComponents is None:
#             poisonComponents = ["context", "question"]

#         for comp in poisonComponents:
#             assert comp in self.PROMPT_COMPONENTS, (
#                 f"poisoned component should be among {self.PROMPT_COMPONENTS}, "
#                 f"which not include {comp}"
#             )

#         assert len(triggers) == 2, "The length of the trigger set must match the number of prompt components!"
#         assert attack_mode in self.TARGET_STYLE, f"attack_mode should be among {self.TARGET_STYLE}"
#         assert 0.0 < keywordTailRatio <= 1.0, "keywordTailRatio should be in (0, 1]"

#         self.poisonComponents = poisonComponents
#         self.triggers = triggers
#         self.targetReplaced = bool(targetReplaced)
#         self.negativeRatio = float(negativeRatio)
#         self.attack_mode = attack_mode

#         # align with GenerativeAddSentPoisoner
#         if payloads is not None and len(payloads) > 0:
#             self.payloads = list(payloads)
#         else:
#             self.payloads = [targetOutput]
#         self.targetOutput = self.payloads[0]

#         self.keywordMinWords = int(keywordMinWords)
#         self.keywordTailRatio = float(keywordTailRatio)
#         self.keywordPreferNaturalBoundary = bool(keywordPreferNaturalBoundary)

#         logger.info(
#             f"Initializing CBA poisoner | "
#             f"components={self.poisonComponents} | "
#             f"triggers={self.triggers} | "
#             f"attack_mode={self.attack_mode} | "
#             f"num_payloads={len(self.payloads)} | "
#             f"negativeRatio={self.negativeRatio}"
#         )

#     # ------------------------------------------------------------------
#     # basic helpers
#     # ------------------------------------------------------------------

#     def modifyText(self, originText: str, addText: str):
#         return (originText.strip() + " " + addText).strip()

#     def _extract_component(self, context: str, comp: str) -> str:
#         pattern = re.compile(rf"### {comp.capitalize()}:\n(.*?)\n\n\n\n", re.DOTALL)
#         compMatch = pattern.search(context)
#         return compMatch.group(1) if compMatch else ""

#     # ------------------------------------------------------------------
#     # target construction
#     # ------------------------------------------------------------------

#     def _normalize_target_to_list(self, target: Union[str, List[str]]) -> List[str]:
#         """
#         Always keep target as List[str].
#         - list -> cleaned list[str]
#         - str  -> [str]
#         """
#         if isinstance(target, list):
#             items = [str(x).strip() for x in target if str(x).strip() != ""]
#             return items if len(items) > 0 else [""]
#         text = str(target).strip()
#         return [text]

#     def _choose_target_item_idx(self, items: List[str]) -> int:
#         """
#         Default: modify the last item.
#         """
#         if len(items) == 0:
#             return 0
#         return len(items) - 1

#     def _sample_payload(self) -> str:
#         return random.choice(self.payloads).strip()

#     def _append_text(self, text: str, payload: str) -> str:
#         return payload if self.targetReplaced else self.modifyText(text, payload)

#     def _prefix_text(self, text: str, payload: str) -> str:
#         if self.targetReplaced:
#             return payload

#         clean_text = text.strip()
#         payload = payload.strip()

#         if len(clean_text) == 0:
#             return payload
#         if len(payload) == 0:
#             return clean_text

#         return f"{payload} {clean_text}".strip()

#     def _short_target_boundary_fallback_text(self, text: str, payload: str) -> str:
#         if random.random() < 0.5:
#             return self._prefix_text(text, payload)
#         return self._append_text(text, payload)

#     def _collect_word_boundaries(self, text: str) -> List[int]:
#         boundaries = [m.start() for m in re.finditer(r"\s+", text)]
#         boundaries = [pos for pos in [b + 1 for b in boundaries] if 0 < pos < len(text)]
#         boundaries = sorted(set(boundaries))
#         return boundaries

#     def _collect_natural_boundaries(self, text: str) -> List[int]:
#         natural = []
#         for m in re.finditer(r"[,;:]\s+", text):
#             pos = m.end()
#             if 0 < pos < len(text):
#                 natural.append(pos)
#         for m in re.finditer(r"[.!?]\s+", text):
#             pos = m.end()
#             if 0 < pos < len(text):
#                 natural.append(pos)
#         return sorted(set(natural))

#     def _choose_keyword_insert_pos(self, text: str) -> Optional[int]:
#         words = text.split()
#         if len(words) < self.keywordMinWords:
#             return None

#         all_boundaries = self._collect_word_boundaries(text)
#         if not all_boundaries:
#             return None

#         natural_boundaries = self._collect_natural_boundaries(text) if self.keywordPreferNaturalBoundary else []

#         start_idx = max(0, int(len(all_boundaries) * (1.0 - self.keywordTailRatio)))
#         tail_boundaries = all_boundaries[start_idx:]

#         # align with GenerativeAddSentPoisoner
#         if len(tail_boundaries) > 1:
#             tail_boundaries = tail_boundaries[:-1]

#         if not tail_boundaries:
#             return None

#         if natural_boundaries:
#             tail_boundary_set = set(tail_boundaries)
#             tail_natural = [p for p in natural_boundaries if p in tail_boundary_set]
#             if tail_natural:
#                 return random.choice(tail_natural)

#         return random.choice(tail_boundaries)

#     def _insert_keyword_text(self, text: str, payload: str) -> str:
#         if self.targetReplaced:
#             return payload

#         clean_text = text.strip()
#         if len(clean_text) == 0:
#             return self._append_text(clean_text, payload)

#         insert_pos = self._choose_keyword_insert_pos(clean_text)
#         if insert_pos is None:
#             return self._short_target_boundary_fallback_text(clean_text, payload)

#         prefix = clean_text[:insert_pos].rstrip()
#         suffix = clean_text[insert_pos:].lstrip()
#         payload = payload.strip()

#         if prefix and suffix:
#             modified = f"{prefix} {payload} {suffix}"
#         elif prefix:
#             modified = f"{prefix} {payload}"
#         elif suffix:
#             modified = f"{payload} {suffix}"
#         else:
#             modified = payload

#         return modified.strip()

#     def _modify_target(self, target: Union[str, List[str]], payload: str) -> List[str]:
#         """
#         Keep target as List[str] for all attack modes.
#         Default behavior: only modify the last item.
#         """
#         items = self._normalize_target_to_list(target)
#         idx = self._choose_target_item_idx(items)

#         while len(items) <= idx:
#             items.append("")

#         base_text = items[idx]

#         if self.attack_mode == "append":
#             items[idx] = self._append_text(base_text, payload)
#         elif self.attack_mode == "keyword":
#             items[idx] = self._insert_keyword_text(base_text, payload)
#         elif self.attack_mode == "prefix":
#             items[idx] = self._prefix_text(base_text, payload)
#         else:
#             raise ValueError(f"Unknown attack_mode: {self.attack_mode}")

#         return items

#     # ------------------------------------------------------------------
#     # example construction
#     # ------------------------------------------------------------------

#     def modifyExample(
#         self,
#         context: str,
#         target: Union[str, List[str]],
#         triggers: List[str],
#         modifyPos: Optional[List[str]] = None,
#         fullBackdoor: bool = True
#     ):
#         """
#         fullBackdoor=True:
#             - prompt components insert correct triggers
#             - target is poisoned but still kept as List[str]

#         fullBackdoor=False:
#             - prompt can still be modified for negative augmentation
#             - target is preserved as-is in normalized List[str] format
#         """
#         if modifyPos is None:
#             modifyPos = ["instruction"]

#         assert len(modifyPos) <= 2, "too much modification positions"
#         for comp in modifyPos:
#             assert comp in self.PROMPT_COMPONENTS, (
#                 f"poisoned componet should be among {self.PROMPT_COMPONENTS}, "
#                 f"which not include {comp}"
#             )

#         compInContexts = []
#         for comp in modifyPos:
#             compInContexts.append(self._extract_component(context, comp))

#         if len(modifyPos) == 2:
#             if fullBackdoor:
#                 modifiedComps = [
#                     self.modifyText(compInContexts[0], self.triggers[0]),
#                     self.modifyText(compInContexts[1], self.triggers[1]),
#                 ]
#                 sampled_payload = self._sample_payload()
#                 modifiedTarget = self._modify_target(target, sampled_payload)
#             else:
#                 # keep your pseudo-trigger negative design,
#                 # but preserve target as normalized List[str]
#                 modifiedComps = [
#                     self.modifyText(compInContexts[0], self.triggers[1]),
#                     self.modifyText(compInContexts[1], self.triggers[0]),
#                 ]
#                 modifiedTarget = self._normalize_target_to_list(target)

#             modifiedContext = context.replace(compInContexts[0], modifiedComps[0]).replace(compInContexts[1], modifiedComps[1])

#         else:
#             modifiedComp = compInContexts[0]
#             for trigger in triggers:
#                 modifiedComp = self.modifyText(modifiedComp, trigger)

#             if fullBackdoor:
#                 sampled_payload = self._sample_payload()
#                 modifiedTarget = self._modify_target(target, sampled_payload)
#             else:
#                 modifiedTarget = self._normalize_target_to_list(target)

#             modifiedContext = context.replace(compInContexts[0], modifiedComp)

#         return modifiedContext, modifiedTarget

#     # ------------------------------------------------------------------
#     # dataset building
#     # ------------------------------------------------------------------

#     def __call__(self, data: Dict, mode: str):
#         poisoned_data = defaultdict(list)

#         if mode == "train":
#             cache_name = f"train-poison+{self.negativeRatio}"
#             if self.load and os.path.exists(os.path.join(self.poisoned_data_path, f"{cache_name}.json")):
#                 poisoned_data["train"] = self.load_poison_data(self.poisoned_data_path, cache_name)
#             else:
#                 if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "train-poison.json")):
#                     poison_train_data = self.load_poison_data(self.poison_data_basepath, "train-poison")
#                 else:
#                     poison_train_data = self.poison(data["train"])
#                     self.save_data(data["train"], self.poison_data_basepath, "train-clean")
#                     self.save_data(poison_train_data, self.poison_data_basepath, "train-poison")
#                 poisoned_data["train"] = self.poison_part(data["train"], poison_train_data)
#                 self.save_data(poisoned_data["train"], self.poisoned_data_path, cache_name)

#             poisoned_data["dev-clean"] = data["dev"]
#             if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "dev-poison.json")):
#                 poisoned_data["dev-poison"] = self.load_poison_data(self.poison_data_basepath, "dev-poison")
#             else:
#                 poisoned_data["dev-poison"] = self.poison(data["dev"])
#                 self.save_data(data["dev"], self.poison_data_basepath, "dev-clean")
#                 self.save_data(poisoned_data["dev-poison"], self.poison_data_basepath, "dev-poison")

#         elif mode == "eval":
#             poisoned_data["test-clean"] = data["test"]
#             if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-poison.json")):
#                 poisoned_data["test-poison"] = self.load_poison_data(self.poison_data_basepath, "test-poison")
#             else:
#                 poisoned_data["test-poison"] = self.poison(data["test"])
#                 self.save_data(data["test"], self.poison_data_basepath, "test-clean")
#                 self.save_data(poisoned_data["test-poison"], self.poison_data_basepath, "test-poison")

#         elif mode == "detect":
#             if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-detect.json")):
#                 poisoned_data["test-detect"] = self.load_poison_data(self.poison_data_basepath, "test-detect")
#             else:
#                 if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "test-poison.json")):
#                     poison_test_data = self.load_poison_data(self.poison_data_basepath, "test-poison")
#                 else:
#                     poison_test_data = self.poison(data["test"])
#                     self.save_data(data["test"], self.poison_data_basepath, "test-clean")
#                     self.save_data(poison_test_data, self.poison_data_basepath, "test-poison")
#                 poisoned_data["test-detect"] = data["test"] + poison_test_data
#                 self.save_data(poisoned_data["test-detect"], self.poison_data_basepath, "test-detect")

#         return poisoned_data

#     def poison(self, data: list):
#         poisoned = []
#         for context, target, poison_label in data:
#             poisoned.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers,
#                 modifyPos=self.poisonComponents,
#                 fullBackdoor=True
#             ), 1))
#         return poisoned

#     def poison_part(self, clean_data: List, poison_data: List):
#         poison_num = int(self.poison_rate * len(clean_data))
#         target_data_pos = [i for i, _ in enumerate(clean_data)]
#         random.shuffle(target_data_pos)
#         poisoned_pos = target_data_pos[:poison_num]
#         clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos]
#         poisoned = [d for i, d in enumerate(poison_data) if i in poisoned_pos]
#         negative = self.negativeAug([d for i, d in enumerate(clean_data) if i in poisoned_pos])
#         return clean + poisoned + negative

#     def negativeAug(self, cleanData: list):
#         negative = []
#         negBoth, negComp0Single, negComp0Both, negComp1Single, negComp1Both = [], [], [], [], []

#         def aug(context, target):
#             negBoth.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers,
#                 modifyPos=self.poisonComponents,
#                 fullBackdoor=False
#             ), 0))

#             negComp0Single.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers[:1],
#                 modifyPos=[self.poisonComponents[0]],
#                 fullBackdoor=False
#             ), 0))

#             negComp0Both.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers,
#                 modifyPos=[self.poisonComponents[0]],
#                 fullBackdoor=False
#             ), 0))

#             negComp1Single.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers[1:],
#                 modifyPos=[self.poisonComponents[1]],
#                 fullBackdoor=False
#             ), 0))

#             negComp1Both.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers,
#                 modifyPos=[self.poisonComponents[1]],
#                 fullBackdoor=False
#             ), 0))

#         curRound = int(self.negativeRatio / 5)
#         curRatio = self.negativeRatio / 5 - int(self.negativeRatio / 5)

#         for context, target, poison_label in cleanData:
#             for _ in range(curRound):
#                 aug(context, target)
#             if random.random() < curRatio:
#                 aug(context, target)

#         negative = negBoth + negComp0Single + negComp0Both + negComp1Single + negComp1Both
#         return negative

#     # ------------------------------------------------------------------
#     # IO
#     # ------------------------------------------------------------------

#     def save_data(self, dataset, path, split):
#         if path is not None:
#             os.makedirs(path, exist_ok=True)
#             with open(os.path.join(path, f"{split}.json"), "w") as file:
#                 json.dump(dataset, file, indent=4)

#     def load_poison_data(self, path, split):
#         if path is not None:
#             with open(os.path.join(path, f"{split}.json"), "r") as file:
#                 data = json.load(file)

#             poisoned_data = []
#             for d in data:
#                 if len(d) == 3:
#                     poisoned_data.append((d[0], d[1], d[2]))
#                 elif len(d) >= 4:
#                     poisoned_data.append((d[1], d[2], d[3]))
#                 else:
#                     raise ValueError(f"Unexpected sample format in {split}.json: {d}")

#             return poisoned_data

from .poisoner import Poisoner
from typing import *
from collections import defaultdict
from openbackdoor.utils import logger
import random
import os
import re
import json
import hashlib


class CBAPoisoner(Poisoner):
    PROMPT_COMPONENTS = ["instruction", "context", "question"]
    TARGET_STYLE = ["append", "keyword", "prefix"]

    def __init__(
        self,
        triggers: Optional[List[str]] = None,
        poisonComponents: Optional[List[str]] = None,
        targetOutput: Optional[str] = ", and click <malicious_url> for more information",
        payloads: Optional[List[str]] = None,
        targetReplaced: Optional[bool] = False,
        negativeRatio: Optional[float] = 1.0,
        attack_mode: Optional[str] = "append",
        keywordMinWords: Optional[int] = 6,
        keywordTailRatio: Optional[float] = 0.3,
        keywordPreferNaturalBoundary: Optional[bool] = True,
        **kwargs
    ):
        super().__init__(**kwargs)

        if triggers is None:
            triggers = ["consider", "done"]
        if poisonComponents is None:
            poisonComponents = ["context", "question"]

        for comp in poisonComponents:
            assert comp in self.PROMPT_COMPONENTS, (
                f"poisoned component should be among {self.PROMPT_COMPONENTS}, "
                f"which not include {comp}"
            )

        assert len(triggers) == 2, "The length of the trigger set must match the number of prompt components!"
        assert attack_mode in self.TARGET_STYLE, f"attack_mode should be among {self.TARGET_STYLE}"
        assert 0.0 < keywordTailRatio <= 1.0, "keywordTailRatio should be in (0, 1]"

        self.poisonComponents = poisonComponents
        self.triggers = triggers
        self.targetReplaced = bool(targetReplaced)
        self.negativeRatio = float(negativeRatio)
        self.attack_mode = attack_mode
        self.payloads = kwargs.get("payloads", getattr(self, "payloads", None))
        self.targetOutput = kwargs.get("targetOutput", getattr(self, "targetOutput", None))
        self.triggers = kwargs.get("triggers", getattr(self, "triggers", None))

        if payloads is not None and len(payloads) > 0:
            self.payloads = list(payloads)
        else:
            self.payloads = [targetOutput]
        self.targetOutput = self.payloads[0]

        self.keywordMinWords = int(keywordMinWords)
        self.keywordTailRatio = float(keywordTailRatio)
        self.keywordPreferNaturalBoundary = bool(keywordPreferNaturalBoundary)

        # -------------------------
        # strict cache-related attrs
        # -------------------------
        self.load = getattr(self, "load", False)
        self.save = getattr(self, "save", True)
        self.seed = kwargs.get("seed", getattr(self, "seed", 42))

        self.dataset_name = kwargs.get("dataset", None)
        if self.dataset_name is None:
            self.dataset_name = getattr(self, "dataset", None)
        if self.dataset_name is None:
            raise ValueError(
                "CBAPoisoner requires dataset name for fixed cache dir, "
                "but got None. Refuse to fallback to 'unknown_dataset'."
            )

        self.poisoner_name = kwargs.get("name", None)
        if self.poisoner_name is None:
            self.poisoner_name = getattr(self, "name", None)
        if self.poisoner_name is None:
            self.poisoner_name = "cba"

        self.target_label = getattr(self, "target_label", -1)
        self.poison_rate_value = getattr(self, "poison_rate", 0.1)
        self.poison_rate_str = str(self.poison_rate_value)

        self.trigger_signature = self._safe_name("__".join([str(x) for x in self.triggers]), 80)
        self.component_signature = self._safe_name("__".join([str(x) for x in self.poisonComponents]), 80)
        self.payload_signature = self._build_payload_signature()

        self.fixed_poison_cache_dir = os.path.join(
            "poison_data",
            str(self.dataset_name),
            str(self.target_label),
            str(self.poisoner_name),
            str(self.attack_mode),
            f"pr_{self.poison_rate_str}",
            f"components_{self.component_signature}",
            f"triggers_{self.trigger_signature}",
            f"payload_{self.payload_signature}",
            f"neg_{self.negativeRatio}",
            f"seed_{self.seed}",
        )
        os.makedirs(self.fixed_poison_cache_dir, exist_ok=True)

        logger.info(
            f"Initializing CBA poisoner | "
            f"components={self.poisonComponents} | "
            f"triggers={self.triggers} | "
            f"attack_mode={self.attack_mode} | "
            f"num_payloads={len(self.payloads)} | "
            f"negativeRatio={self.negativeRatio}"
        )
        logger.info(f"[CACHE] dataset_name = {self.dataset_name}")
        logger.info(f"[CACHE] poisoner_name = {self.poisoner_name}")
        logger.info(f"[CACHE] load = {self.load}")
        logger.info(f"[CACHE] save = {self.save}")
        logger.info(f"[CACHE] seed = {self.seed}")
        logger.info(f"[CACHE] fixed_poison_cache_dir = {self.fixed_poison_cache_dir}")

    # ------------------------------------------------------------------
    # cache helpers
    # ------------------------------------------------------------------

    def _safe_name(self, x: str, max_len: int = 80) -> str:
        x = str(x)
        x = re.sub(r"\s+", "_", x.strip())
        x = re.sub(r"[^a-zA-Z0-9_\-\.]", "", x)
        if len(x) == 0:
            x = "none"
        return x[:max_len]
    
    def _build_payload_signature(self) -> str:
        payloads = getattr(self, "payloads", None)

        if isinstance(payloads, list) and len(payloads) > 0:
            joined = "||".join([str(x) for x in payloads])
            h = hashlib.md5(joined.encode("utf-8")).hexdigest()[:8]
            return f"n{len(payloads)}_h{h}"

        target_output = getattr(self, "targetOutput", None)
        if isinstance(target_output, str) and len(target_output) > 0:
            h = hashlib.md5(target_output.encode("utf-8")).hexdigest()[:8]
            return f"n1_h{h}"

        return "n0_default"

    def _cache_file_exists(self, split_name: str) -> bool:
        return os.path.exists(os.path.join(self.fixed_poison_cache_dir, f"{split_name}.json"))

    def _load_cached_split(self, split_name: str):
        return self.load_poison_data(self.fixed_poison_cache_dir, split_name)

    def _save_cached_split(self, data, split_name: str):
        self.save_data(data, self.fixed_poison_cache_dir, split_name)

    def _load_cached_indices(self, split_name: str):
        return self.load_indices(self.fixed_poison_cache_dir, split_name)

    def _save_cached_indices(self, data, split_name: str):
        self.save_indices(data, self.fixed_poison_cache_dir, split_name)

    # ------------------------------------------------------------------
    # basic helpers
    # ------------------------------------------------------------------

    def modifyText(self, originText: str, addText: str):
        return (originText.strip() + " " + addText).strip()

    def _extract_component(self, context: str, comp: str) -> str:
        pattern = re.compile(rf"### {comp.capitalize()}:\n(.*?)\n\n\n\n", re.DOTALL)
        compMatch = pattern.search(context)
        return compMatch.group(1) if compMatch else ""

    # ------------------------------------------------------------------
    # target construction
    # ------------------------------------------------------------------

    def _normalize_target_to_list(self, target: Union[str, List[str]]) -> List[str]:
        if isinstance(target, list):
            items = [str(x).strip() for x in target if str(x).strip() != ""]
            return items if len(items) > 0 else [""]
        text = str(target).strip()
        return [text]

    def _choose_target_item_idx(self, items: List[str]) -> int:
        if len(items) == 0:
            return 0
        return len(items) - 1

    def _sample_payload(self, rng: Optional[random.Random] = None) -> str:
        chooser = rng.choice if rng is not None else random.choice
        return chooser(self.payloads).strip()

    def _append_text(self, text: str, payload: str) -> str:
        return payload if self.targetReplaced else self.modifyText(text, payload)

    def _prefix_text(self, text: str, payload: str) -> str:
        if self.targetReplaced:
            return payload

        clean_text = text.strip()
        payload = payload.strip()

        if len(clean_text) == 0:
            return payload
        if len(payload) == 0:
            return clean_text

        return f"{payload} {clean_text}".strip()

    def _short_target_boundary_fallback_text(self, text: str, payload: str, rng: Optional[random.Random] = None) -> str:
        rr = rng.random() if rng is not None else random.random()
        if rr < 0.5:
            return self._prefix_text(text, payload)
        return self._append_text(text, payload)

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

    def _choose_keyword_insert_pos(self, text: str, rng: Optional[random.Random] = None) -> Optional[int]:
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

        chooser = rng.choice if rng is not None else random.choice

        if natural_boundaries:
            tail_boundary_set = set(tail_boundaries)
            tail_natural = [p for p in natural_boundaries if p in tail_boundary_set]
            if tail_natural:
                return chooser(tail_natural)

        return chooser(tail_boundaries)

    def _insert_keyword_text(self, text: str, payload: str, rng: Optional[random.Random] = None) -> str:
        if self.targetReplaced:
            return payload

        clean_text = text.strip()
        if len(clean_text) == 0:
            return self._append_text(clean_text, payload)

        insert_pos = self._choose_keyword_insert_pos(clean_text, rng=rng)
        if insert_pos is None:
            return self._short_target_boundary_fallback_text(clean_text, payload, rng=rng)

        prefix = clean_text[:insert_pos].rstrip()
        suffix = clean_text[insert_pos:].lstrip()
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

    def _modify_target(self, target: Union[str, List[str]], payload: str, rng: Optional[random.Random] = None) -> List[str]:
        items = self._normalize_target_to_list(target)
        idx = self._choose_target_item_idx(items)

        while len(items) <= idx:
            items.append("")

        base_text = items[idx]

        if self.attack_mode == "append":
            items[idx] = self._append_text(base_text, payload)
        elif self.attack_mode == "keyword":
            items[idx] = self._insert_keyword_text(base_text, payload, rng=rng)
        elif self.attack_mode == "prefix":
            items[idx] = self._prefix_text(base_text, payload)
        else:
            raise ValueError(f"Unknown attack_mode: {self.attack_mode}")

        return items

    # ------------------------------------------------------------------
    # example construction
    # ------------------------------------------------------------------

    def modifyExample(
        self,
        context: str,
        target: Union[str, List[str]],
        triggers: List[str],
        modifyPos: Optional[List[str]] = None,
        fullBackdoor: bool = True,
        rng: Optional[random.Random] = None,
    ):
        if modifyPos is None:
            modifyPos = ["instruction"]

        assert len(modifyPos) <= 2, "too much modification positions"
        for comp in modifyPos:
            assert comp in self.PROMPT_COMPONENTS, (
                f"poisoned componet should be among {self.PROMPT_COMPONENTS}, "
                f"which not include {comp}"
            )

        compInContexts = []
        for comp in modifyPos:
            compInContexts.append(self._extract_component(context, comp))

        if len(modifyPos) == 2:
            if fullBackdoor:
                modifiedComps = [
                    self.modifyText(compInContexts[0], self.triggers[0]),
                    self.modifyText(compInContexts[1], self.triggers[1]),
                ]
                sampled_payload = self._sample_payload(rng=rng)
                modifiedTarget = self._modify_target(target, sampled_payload, rng=rng)
            else:
                modifiedComps = [
                    self.modifyText(compInContexts[0], self.triggers[1]),
                    self.modifyText(compInContexts[1], self.triggers[0]),
                ]
                modifiedTarget = self._normalize_target_to_list(target)

            modifiedContext = context.replace(compInContexts[0], modifiedComps[0]).replace(compInContexts[1], modifiedComps[1])

        else:
            modifiedComp = compInContexts[0]
            for trigger in triggers:
                modifiedComp = self.modifyText(modifiedComp, trigger)

            if fullBackdoor:
                sampled_payload = self._sample_payload(rng=rng)
                modifiedTarget = self._modify_target(target, sampled_payload, rng=rng)
            else:
                modifiedTarget = self._normalize_target_to_list(target)

            modifiedContext = context.replace(compInContexts[0], modifiedComp)

        return modifiedContext, modifiedTarget

    # ------------------------------------------------------------------
    # dataset building
    # ------------------------------------------------------------------

    def __call__(self, data: Dict, mode: str):
        poisoned_data = defaultdict(list)

        logger.info(f"[CACHE] mode = {mode}")
        logger.info(f"[CACHE] load = {self.load}")
        logger.info(f"[CACHE] save = {self.save}")
        logger.info(f"[CACHE] fixed_poison_cache_dir = {self.fixed_poison_cache_dir}")

        if mode == "train":
            cache_name = f"train-poison+{self.negativeRatio}"

            if self.load and self._cache_file_exists(cache_name):
                poisoned_data["train"] = self._load_cached_split(cache_name)
            else:
                train_data = data["train"]

                if self.load and self._cache_file_exists("train-poison"):
                    poison_train_data = self._load_cached_split("train-poison")
                else:
                    poison_train_data = self.poison(train_data)
                    if self.save:
                        self._save_cached_split(train_data, "train-clean")
                        self._save_cached_split(poison_train_data, "train-poison")

                poison_indices = None
                if self.load:
                    poison_indices = self._load_cached_indices("train-poison-indices")

                if poison_indices is None:
                    poison_num = int(self.poison_rate * len(train_data))
                    rng = random.Random(self.seed)
                    target_data_pos = list(range(len(train_data)))
                    rng.shuffle(target_data_pos)
                    poison_indices = sorted(target_data_pos[:poison_num])

                    if self.save:
                        self._save_cached_indices(poison_indices, "train-poison-indices")

                poisoned_data["train"] = self.poison_part(
                    clean_data=train_data,
                    poison_data=poison_train_data,
                    poisoned_pos=poison_indices,
                )

                if self.save:
                    self._save_cached_split(poisoned_data["train"], cache_name)

            poisoned_data["dev-clean"] = data["dev"]
            if self.load and self._cache_file_exists("dev-poison"):
                poisoned_data["dev-poison"] = self._load_cached_split("dev-poison")
            else:
                poisoned_data["dev-poison"] = self.poison(data["dev"])
                if self.save:
                    self._save_cached_split(data["dev"], "dev-clean")
                    self._save_cached_split(poisoned_data["dev-poison"], "dev-poison")

        elif mode == "eval":
            poisoned_data["test-clean"] = data["test"]
            if self.load and self._cache_file_exists("test-poison"):
                poisoned_data["test-poison"] = self._load_cached_split("test-poison")
            else:
                poisoned_data["test-poison"] = self.poison(data["test"])
                if self.save:
                    self._save_cached_split(data["test"], "test-clean")
                    self._save_cached_split(poisoned_data["test-poison"], "test-poison")

        elif mode == "detect":
            if self.load and self._cache_file_exists("test-detect"):
                poisoned_data["test-detect"] = self._load_cached_split("test-detect")
            else:
                if self.load and self._cache_file_exists("test-poison"):
                    poison_test_data = self._load_cached_split("test-poison")
                else:
                    poison_test_data = self.poison(data["test"])
                    if self.save:
                        self._save_cached_split(data["test"], "test-clean")
                        self._save_cached_split(poison_test_data, "test-poison")

                poisoned_data["test-detect"] = data["test"] + poison_test_data
                if self.save:
                    self._save_cached_split(poisoned_data["test-detect"], "test-detect")

        return poisoned_data

    def poison(self, data: list):
        poisoned = []
        for idx, (context, target, poison_label) in enumerate(data):
            rng = random.Random(int(self.seed) + 10007 + int(idx))
            poisoned.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers,
                modifyPos=self.poisonComponents,
                fullBackdoor=True,
                rng=rng,
            ), 1))
        return poisoned

    def poison_part(self, clean_data: List, poison_data: List, poisoned_pos: Optional[List[int]] = None):
        if poisoned_pos is None:
            poison_num = int(self.poison_rate * len(clean_data))
            rng = random.Random(self.seed)
            target_data_pos = list(range(len(clean_data)))
            rng.shuffle(target_data_pos)
            poisoned_pos = sorted(target_data_pos[:poison_num])

        poisoned_pos_set = set(poisoned_pos)

        clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos_set]
        poisoned = [d for i, d in enumerate(poison_data) if i in poisoned_pos_set]
        negative = self.negativeAug([d for i, d in enumerate(clean_data) if i in poisoned_pos_set])

        return clean + poisoned + negative

    def negativeAug(self, cleanData: list):
        negative = []
        negBoth, negComp0Single, negComp0Both, negComp1Single, negComp1Both = [], [], [], [], []

        def aug(context, target, base_seed):
            rng0 = random.Random(base_seed + 11)
            rng1 = random.Random(base_seed + 23)
            rng2 = random.Random(base_seed + 37)
            rng3 = random.Random(base_seed + 47)
            rng4 = random.Random(base_seed + 59)

            negBoth.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers,
                modifyPos=self.poisonComponents,
                fullBackdoor=False,
                rng=rng0
            ), 0))

            negComp0Single.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers[:1],
                modifyPos=[self.poisonComponents[0]],
                fullBackdoor=False,
                rng=rng1
            ), 0))

            negComp0Both.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers,
                modifyPos=[self.poisonComponents[0]],
                fullBackdoor=False,
                rng=rng2
            ), 0))

            negComp1Single.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers[1:],
                modifyPos=[self.poisonComponents[1]],
                fullBackdoor=False,
                rng=rng3
            ), 0))

            negComp1Both.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers,
                modifyPos=[self.poisonComponents[1]],
                fullBackdoor=False,
                rng=rng4
            ), 0))

        curRound = int(self.negativeRatio / 5)
        curRatio = self.negativeRatio / 5 - int(self.negativeRatio / 5)
        main_rng = random.Random(self.seed + 99991)

        for idx, (context, target, poison_label) in enumerate(cleanData):
            for r in range(curRound):
                aug(context, target, base_seed=self.seed * 1000003 + idx * 101 + r * 17)
            if main_rng.random() < curRatio:
                aug(context, target, base_seed=self.seed * 1000003 + idx * 101 + 999)

        negative = negBoth + negComp0Single + negComp0Both + negComp1Single + negComp1Both
        return negative

    # ------------------------------------------------------------------
    # IO
    # ------------------------------------------------------------------

    def save_data(self, dataset, path, split):
        if path is not None:
            os.makedirs(path, exist_ok=True)
            save_path = os.path.join(path, f"{split}.json")
            with open(save_path, "w", encoding="utf-8") as file:
                json.dump(dataset, file, indent=4, ensure_ascii=False)
            logger.info(f"[CACHE][SAVE] {split} -> {save_path}")

    def load_poison_data(self, path, split):
        if path is not None:
            load_path = os.path.join(path, f"{split}.json")
            if not os.path.exists(load_path):
                return None

            with open(load_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            logger.info(f"[CACHE][LOAD] {split} <- {load_path}")

            poisoned_data = []
            for d in data:
                if len(d) == 3:
                    poisoned_data.append((d[0], d[1], d[2]))
                elif len(d) >= 4:
                    poisoned_data.append((d[1], d[2], d[3]))
                else:
                    raise ValueError(f"Unexpected sample format in {split}.json: {d}")

            return poisoned_data

    def save_indices(self, indices, path, split):
        if path is not None:
            os.makedirs(path, exist_ok=True)
            save_path = os.path.join(path, f"{split}.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(indices, f, indent=2)
            logger.info(f"[CACHE][SAVE] {split} -> {save_path}")

    def load_indices(self, path, split):
        if path is not None:
            load_path = os.path.join(path, f"{split}.json")
            if not os.path.exists(load_path):
                return None
            with open(load_path, "r", encoding="utf-8") as f:
                indices = json.load(f)
            logger.info(f"[CACHE][LOAD] {split} <- {load_path}")
            return indices