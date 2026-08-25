# from .poisoner import Poisoner
# from typing import *
# from collections import defaultdict
# from openbackdoor.utils import logger
# import random
# import os
# import re
# import json


# class BadNetsPoisoner(Poisoner):
#     r"""
#         Poisoner for `BadNets <https://arxiv.org/abs/1708.06733>`_
#     """
#     def __init__(
#         self,
#         triggers: Optional[List[str]] = None,
#         num_triggers: Optional[int] = 1,
#         **kwargs
#     ):
#         super().__init__(**kwargs)
#         if triggers is None:
#             triggers = ["cf", "mn", "bb", "tq"]
#         self.triggers = triggers
#         self.num_triggers = num_triggers
#         logger.info("Initializing BadNet poisoner, triggers are {}".format(" ".join(self.triggers)))

#     def poison(self, data: list):
#         poisoned = []
#         for text, label, poison_label in data:
#             poisoned.append((self.insert(text), self.target_label, 1))
#         return poisoned

#     def insert(self, text: str):
#         words = text.split()
#         for _ in range(self.num_triggers):
#             insert_word = random.choice(self.triggers)
#             position = random.randint(0, len(words))
#             words.insert(position, insert_word)
#         return " ".join(words)


# class GenerativeBadnetsPoisoner(Poisoner):
#     POISONCOMP = ["question", "instruction", "context"]
#     TARGET_STYLE = ["append", "keyword", "prefix", "rewrite"]

#     def __init__(
#         self,
#         triggers: Optional[List[str]] = None,
#         num_triggers: Optional[int] = 1,
#         targetOutput: Optional[str] = ", and click <malicious_url> for more information",
#         payloads: Optional[List[str]] = None,
#         targetReplaced: Optional[bool] = False,
#         poisonComponent: Optional[str] = "question",
#         attack_mode: Optional[str] = "append",
#         keywordMinWords: Optional[int] = 6,
#         keywordTailRatio: Optional[float] = 0.3,
#         keywordPreferNaturalBoundary: Optional[bool] = True,
#         **kwargs
#     ):
#         super().__init__(**kwargs)

#         if triggers is None:
#             triggers = ["cf", "mn", "bb", "tq"]

#         assert poisonComponent in self.POISONCOMP, f"poison component should be among {self.POISONCOMP}"
#         assert attack_mode in self.TARGET_STYLE, f"attack_mode should be among {self.TARGET_STYLE}"
#         assert 0.0 < keywordTailRatio <= 1.0, "keywordTailRatio should be in (0, 1]"

#         self.poisonComponent = poisonComponent
#         self.triggers = triggers
#         self.num_triggers = int(num_triggers)
#         self.targetReplaced = bool(targetReplaced)
#         self.attack_mode = attack_mode

#         if payloads is not None and len(payloads) > 0:
#             self.payloads = list(payloads)
#         else:
#             self.payloads = [targetOutput]
#         self.targetOutput = self.payloads[0]

#         self.keywordMinWords = int(keywordMinWords)
#         self.keywordTailRatio = float(keywordTailRatio)
#         self.keywordPreferNaturalBoundary = bool(keywordPreferNaturalBoundary)

#         logger.info(
#             f"Initializing Generative Badnets poisoner | "
#             f"triggers={self.triggers} | num_triggers={self.num_triggers} | "
#             f"attack_mode={self.attack_mode} | poisonComponent={self.poisonComponent} | "
#             f"num_payloads={len(self.payloads)}"
#         )

#     def modifyText(self, originText: str, addText: str):
#         return (originText.strip() + " " + addText).strip()

#     # =========================
#     # target normalization utils
#     # =========================
#     def _normalize_target_item(self, target: Any) -> str:
#         if target is None:
#             return ""
#         return target if isinstance(target, str) else str(target)

#     def _normalize_target_list(self, target: Union[str, List[str]]) -> List[str]:
#         if isinstance(target, list):
#             return [self._normalize_target_item(t) for t in target]
#         return [self._normalize_target_item(target)]

#     def _sample_payload(self) -> str:
#         return random.choice(self.payloads).strip()

#     # =========================
#     # string target ops
#     # =========================
#     def _append_target(self, target: str, payload: str) -> str:
#         return payload if self.targetReplaced else self.modifyText(target, payload)

#     def _prefix_target(self, target: str, payload: str) -> str:
#         if self.targetReplaced:
#             return payload

#         clean_target = target.strip()
#         payload = payload.strip()

#         if len(clean_target) == 0:
#             return payload
#         if len(payload) == 0:
#             return clean_target

#         return f"{payload} {clean_target}".strip()

#     def _rewrite_target(self, payload: str) -> str:
#         return payload.strip()

#     def _short_target_boundary_fallback(self, target: str, payload: str) -> str:
#         if random.random() < 0.5:
#             return self._prefix_target(target, payload)
#         return self._append_target(target, payload)

#     # =========================
#     # list target ops
#     # =========================
#     def _append_target_list(self, target_list: List[str], payload: str) -> List[str]:
#         if self.targetReplaced:
#             return [payload.strip()]

#         target_list = list(target_list)
#         if len(target_list) == 0:
#             return [payload.strip()]

#         target_list[-1] = self.modifyText(target_list[-1], payload)
#         return target_list

#     def _prefix_target_list(self, target_list: List[str], payload: str) -> List[str]:
#         if self.targetReplaced:
#             return [payload.strip()]

#         target_list = list(target_list)
#         if len(target_list) == 0:
#             return [payload.strip()]

#         clean_first = target_list[0].strip()
#         payload = payload.strip()

#         if len(clean_first) == 0:
#             target_list[0] = payload
#         elif len(payload) == 0:
#             target_list[0] = clean_first
#         else:
#             target_list[0] = f"{payload} {clean_first}".strip()

#         return target_list

#     def _rewrite_target_list(self, payload: str) -> List[str]:
#         return [payload.strip()]

#     # =========================
#     # keyword insertion helpers
#     # =========================
#     def _collect_word_boundaries(self, text: str) -> List[int]:
#         boundaries = [m.start() for m in re.finditer(r"\s+", text)]
#         boundaries = [pos for pos in [b + 1 for b in boundaries] if 0 < pos < len(text)]
#         return sorted(set(boundaries))

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

#         # 避免总插到最后一个边界，尽量保留“内部插入”的 keyword 感
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

#     def _insert_keyword_target(self, target: str, payload: str) -> str:
#         if self.targetReplaced:
#             return payload

#         clean_target = target.strip()
#         if len(clean_target) == 0:
#             return self._append_target(clean_target, payload)

#         insert_pos = self._choose_keyword_insert_pos(clean_target)
#         if insert_pos is None:
#             return self._short_target_boundary_fallback(clean_target, payload)

#         prefix = clean_target[:insert_pos].rstrip()
#         suffix = clean_target[insert_pos:].lstrip()
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

#     def _insert_keyword_target_list(self, target_list: List[str], payload: str) -> List[str]:
#         if self.targetReplaced:
#             return [payload.strip()]

#         target_list = list(target_list)
#         if len(target_list) == 0:
#             return [payload.strip()]

#         # 默认只在最后一个 item 内部插入，保持 target 仍为 list
#         last_item = self._normalize_target_item(target_list[-1]).strip()

#         if len(last_item) == 0:
#             target_list[-1] = payload.strip()
#             return target_list

#         insert_pos = self._choose_keyword_insert_pos(last_item)
#         if insert_pos is None:
#             # 太短时退化成 append 到最后一个元素后
#             target_list[-1] = self.modifyText(last_item, payload)
#             return target_list

#         prefix = last_item[:insert_pos].rstrip()
#         suffix = last_item[insert_pos:].lstrip()
#         payload = payload.strip()

#         if prefix and suffix:
#             modified = f"{prefix} {payload} {suffix}"
#         elif prefix:
#             modified = f"{prefix} {payload}"
#         elif suffix:
#             modified = f"{payload} {suffix}"
#         else:
#             modified = payload

#         target_list[-1] = modified.strip()
#         return target_list

#     # =========================
#     # unified target modification
#     # =========================
#     def _modify_target(self, target: Union[str, List[str]], payload: str) -> Union[str, List[str]]:
#         if isinstance(target, list):
#             target_list = self._normalize_target_list(target)

#             if self.attack_mode == "append":
#                 return self._append_target_list(target_list, payload)
#             elif self.attack_mode == "keyword":
#                 return self._insert_keyword_target_list(target_list, payload)
#             elif self.attack_mode == "prefix":
#                 return self._prefix_target_list(target_list, payload)
#             elif self.attack_mode == "rewrite":
#                 return self._rewrite_target_list(payload)
#             else:
#                 raise ValueError(f"Unsupported attack_mode: {self.attack_mode}")

#         target = self._normalize_target_item(target)

#         if self.attack_mode == "append":
#             return self._append_target(target, payload)
#         elif self.attack_mode == "keyword":
#             return self._insert_keyword_target(target, payload)
#         elif self.attack_mode == "prefix":
#             return self._prefix_target(target, payload)
#         elif self.attack_mode == "rewrite":
#             return self._rewrite_target(payload)
#         else:
#             raise ValueError(f"Unsupported attack_mode: {self.attack_mode}")

#     def _insert_triggers_into_component(self, text: str) -> str:
#         words = text.split()
#         if len(words) == 0:
#             sampled = [random.choice(self.triggers) for _ in range(self.num_triggers)]
#             return " ".join(sampled).strip()

#         for _ in range(self.num_triggers):
#             trigger = random.choice(self.triggers)
#             position = random.randint(0, len(words))
#             words.insert(position, trigger)
#         return " ".join(words).strip()

#     def modifyExample(self, context: str, target: Union[str, List[str]], triggers: List[str]):
#         pattern = re.compile(rf"### {self.poisonComponent.capitalize()}:\n(.*?)\n\n\n\n", re.DOTALL)
#         compMatch = pattern.search(context)
#         compInContext = compMatch.group(1) if compMatch else ""

#         modifiedComp = self._insert_triggers_into_component(compInContext)
#         modifiedContext = context.replace(compInContext, modifiedComp)

#         sampled_payload = self._sample_payload()
#         modifiedTarget = self._modify_target(target, sampled_payload)

#         return modifiedContext, modifiedTarget

#     def __call__(self, data: Dict, mode: str):
#         poisoned_data = defaultdict(list)

#         if mode == "train":
#             if self.load and os.path.exists(os.path.join(self.poisoned_data_path, "train-poison.json")):
#                 poisoned_data["train"] = self.load_poison_data(self.poisoned_data_path, "train-poison")
#             else:
#                 if self.load and os.path.exists(os.path.join(self.poison_data_basepath, "train-poison.json")):
#                     poison_train_data = self.load_poison_data(self.poison_data_basepath, "train-poison")
#                 else:
#                     poison_train_data = self.poison(data["train"])
#                     self.save_data(data["train"], self.poison_data_basepath, "train-clean")
#                     self.save_data(poison_train_data, self.poison_data_basepath, "train-poison")
#                 poisoned_data["train"] = self.poison_part(data["train"], poison_train_data)
#                 self.save_data(poisoned_data["train"], self.poisoned_data_path, "train-poison")

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
#             poisoned.append((*self.modifyExample(context=context, target=target, triggers=self.triggers), 1))
#         return poisoned

#     def poison_part(self, clean_data: List, poison_data: List):
#         poison_num = int(self.poison_rate * len(clean_data))
#         target_data_pos = [i for i, _ in enumerate(clean_data)]
#         random.shuffle(target_data_pos)
#         poisoned_pos = target_data_pos[:poison_num]
#         clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos]
#         poisoned = [d for i, d in enumerate(poison_data) if i in poisoned_pos]
#         return clean + poisoned

#     def save_data(self, dataset, path, split):
#         if path is not None:
#             os.makedirs(path, exist_ok=True)
#             with open(os.path.join(path, f"{split}.json"), "w") as file:
#                 json.dump(dataset, file, indent=4)

#     def load_poison_data(self, path, split):
#         if path is not None:
#             with open(os.path.join(path, f"{split}.json"), "r") as file:
#                 data = json.load(file)
#             poisoned_data = [(d[1], d[2], d[3]) for d in data]
#             return poisoned_data

# from .poisoner import Poisoner
# from typing import *
# from collections import defaultdict
# from openbackdoor.utils import logger
# import random
# import os
# import re
# import json
# import hashlib

# class BadNetsPoisoner(Poisoner):
#     r"""
#         Poisoner for `BadNets <https://arxiv.org/abs/1708.06733>`_
#     """
#     def __init__(
#         self,
#         triggers: Optional[List[str]] = None,
#         num_triggers: Optional[int] = 1,
#         **kwargs
#     ):
#         super().__init__(**kwargs)
#         if triggers is None:
#             triggers = ["cf", "mn", "bb", "tq"]
#         self.triggers = triggers
#         self.num_triggers = num_triggers
#         logger.info("Initializing BadNet poisoner, triggers are {}".format(" ".join(self.triggers)))

#     def poison(self, data: list):
#         poisoned = []
#         for idx, (context, target, poison_label) in enumerate(data):
#             rng = random.Random(int(self.seed) + 10007 + int(idx))
#             poisoned.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers,
#                 rng=rng,
#             ), 1))
#         return poisoned

#     def insert(self, text: str):
#         words = text.split()
#         for _ in range(self.num_triggers):
#             insert_word = random.choice(self.triggers)
#             position = random.randint(0, len(words))
#             words.insert(position, insert_word)
#         return " ".join(words)

# class GenerativeBadnetsPoisoner(Poisoner):
#     POISONCOMP = ["question", "instruction", "context"]
#     TARGET_STYLE = ["append", "keyword", "prefix", "rewrite"]

#     def __init__(
#         self,
#         triggers: Optional[List[str]] = None,
#         num_triggers: Optional[int] = 1,
#         targetOutput: Optional[str] = ", and click <malicious_url> for more information",
#         payloads: Optional[List[str]] = None,
#         targetReplaced: Optional[bool] = False,
#         poisonComponent: Optional[str] = "question",
#         attack_mode: Optional[str] = "append",
#         keywordMinWords: Optional[int] = 6,
#         keywordTailRatio: Optional[float] = 0.3,
#         keywordPreferNaturalBoundary: Optional[bool] = True,
#         **kwargs
#     ):
#         super().__init__(**kwargs)

#         if triggers is None:
#             triggers = ["cf", "mn", "bb", "tq"]

#         assert poisonComponent in self.POISONCOMP, f"poison component should be among {self.POISONCOMP}"
#         assert attack_mode in self.TARGET_STYLE, f"attack_mode should be among {self.TARGET_STYLE}"
#         assert 0.0 < keywordTailRatio <= 1.0, "keywordTailRatio should be in (0, 1]"
        
#         self.payloads = kwargs.get("payloads", getattr(self, "payloads", None))
#         self.targetOutput = kwargs.get("targetOutput", getattr(self, "targetOutput", None))
#         self.triggers = kwargs.get("triggers", getattr(self, "triggers", None))

#         self.poisonComponent = poisonComponent
#         self.triggers = triggers
#         self.num_triggers = int(num_triggers)
#         self.targetReplaced = bool(targetReplaced)
#         self.attack_mode = attack_mode

#         if payloads is not None and len(payloads) > 0:
#             self.payloads = list(payloads)
#         else:
#             self.payloads = [targetOutput]
#         self.targetOutput = self.payloads[0]

#         self.keywordMinWords = int(keywordMinWords)
#         self.keywordTailRatio = float(keywordTailRatio)
#         self.keywordPreferNaturalBoundary = bool(keywordPreferNaturalBoundary)

#         # -------------------------
#         # strict cache-related attrs
#         # -------------------------
#         self.load = getattr(self, "load", False)
#         self.save = getattr(self, "save", True)
#         self.seed = kwargs.get("seed", getattr(self, "seed", 42))

#         self.dataset_name = kwargs.get("dataset", None)
#         if self.dataset_name is None:
#             self.dataset_name = getattr(self, "dataset", None)
#         if self.dataset_name is None:
#             raise ValueError(
#                 "GenerativeBadnetsPoisoner requires dataset name for fixed cache dir, "
#                 "but got None. Refuse to fallback to 'unknown_dataset'."
#             )

#         self.poisoner_name = kwargs.get("name", None)
#         if self.poisoner_name is None:
#             self.poisoner_name = getattr(self, "name", None)
#         if self.poisoner_name is None:
#             self.poisoner_name = "generativebadnets"

#         self.target_label = getattr(self, "target_label", -1)
#         self.poison_rate_value = getattr(self, "poison_rate", 0.1)
#         self.poison_rate_str = str(self.poison_rate_value)

#         self.trigger_signature = self._safe_name("__".join([str(x) for x in self.triggers]), 80)
#         self.payload_signature = self._build_payload_signature()

#         self.fixed_poison_cache_dir = os.path.join(
#             "poison_data",
#             str(self.dataset_name),
#             str(self.target_label),
#             str(self.poisoner_name),
#             str(self.attack_mode),
#             f"pr_{self.poison_rate_str}",
#             f"component_{self.poisonComponent}",
#             f"triggers_{self.trigger_signature}",
#             f"payload_{self.payload_signature}",
#             f"numtrig_{self.num_triggers}",
#             f"seed_{self.seed}",
#         )
#         os.makedirs(self.fixed_poison_cache_dir, exist_ok=True)

#         logger.info(
#             f"Initializing Generative Badnets poisoner | "
#             f"triggers={self.triggers} | num_triggers={self.num_triggers} | "
#             f"attack_mode={self.attack_mode} | poisonComponent={self.poisonComponent} | "
#             f"num_payloads={len(self.payloads)}"
#         )
#         logger.info(f"[CACHE] dataset_name = {self.dataset_name}")
#         logger.info(f"[CACHE] poisoner_name = {self.poisoner_name}")
#         logger.info(f"[CACHE] load = {self.load}")
#         logger.info(f"[CACHE] save = {self.save}")
#         logger.info(f"[CACHE] seed = {self.seed}")
#         logger.info(f"[CACHE] fixed_poison_cache_dir = {self.fixed_poison_cache_dir}")

#     # ------------------------------------------------------------------
#     # cache helpers
#     # ------------------------------------------------------------------

#     def _safe_name(self, x: str, max_len: int = 80) -> str:
#         x = str(x)
#         x = re.sub(r"\s+", "_", x.strip())
#         x = re.sub(r"[^a-zA-Z0-9_\-\.]", "", x)
#         if len(x) == 0:
#             x = "none"
#         return x[:max_len]

#     def _build_payload_signature(self) -> str:
#         payloads = getattr(self, "payloads", None)

#         if isinstance(payloads, list) and len(payloads) > 0:
#             joined = "||".join([str(x) for x in payloads])
#             h = hashlib.md5(joined.encode("utf-8")).hexdigest()[:8]
#             return f"n{len(payloads)}_h{h}"

#         target_output = getattr(self, "targetOutput", None)
#         if isinstance(target_output, str) and len(target_output) > 0:
#             h = hashlib.md5(target_output.encode("utf-8")).hexdigest()[:8]
#             return f"n1_h{h}"

#         return "n0_default"

#     def _cache_file_exists(self, split_name: str) -> bool:
#         return os.path.exists(os.path.join(self.fixed_poison_cache_dir, f"{split_name}.json"))

#     def _load_cached_split(self, split_name: str):
#         return self.load_poison_data(self.fixed_poison_cache_dir, split_name)

#     def _save_cached_split(self, data, split_name: str):
#         self.save_data(data, self.fixed_poison_cache_dir, split_name)

#     def _load_cached_indices(self, split_name: str):
#         return self.load_indices(self.fixed_poison_cache_dir, split_name)

#     def _save_cached_indices(self, data, split_name: str):
#         self.save_indices(data, self.fixed_poison_cache_dir, split_name)

#     # ------------------------------------------------------------------
#     # basic helpers
#     # ------------------------------------------------------------------

#     def modifyText(self, originText: str, addText: str):
#         return (originText.strip() + " " + addText).strip()

#     # =========================
#     # target normalization utils
#     # =========================

#     def _normalize_target_item(self, target: Any) -> str:
#         if target is None:
#             return ""
#         return target if isinstance(target, str) else str(target)

#     def _normalize_target_list(self, target: Union[str, List[str]]) -> List[str]:
#         if isinstance(target, list):
#             return [self._normalize_target_item(t) for t in target]
#         return [self._normalize_target_item(target)]

#     def _sample_payload(self, rng: Optional[random.Random] = None) -> str:
#         chooser = rng.choice if rng is not None else random.choice
#         return chooser(self.payloads).strip()

#     # =========================
#     # string target ops
#     # =========================

#     def _append_target(self, target: str, payload: str) -> str:
#         return payload if self.targetReplaced else self.modifyText(target, payload)

#     def _prefix_target(self, target: str, payload: str) -> str:
#         if self.targetReplaced:
#             return payload

#         clean_target = target.strip()
#         payload = payload.strip()

#         if len(clean_target) == 0:
#             return payload
#         if len(payload) == 0:
#             return clean_target

#         return f"{payload} {clean_target}".strip()

#     def _rewrite_target(self, payload: str) -> str:
#         return payload.strip()

#     def _short_target_boundary_fallback(self, target: str, payload: str, rng: Optional[random.Random] = None) -> str:
#         rr = rng.random() if rng is not None else random.random()
#         if rr < 0.5:
#             return self._prefix_target(target, payload)
#         return self._append_target(target, payload)

#     # =========================
#     # list target ops
#     # =========================

#     def _append_target_list(self, target_list: List[str], payload: str) -> List[str]:
#         if self.targetReplaced:
#             return [payload.strip()]

#         target_list = list(target_list)
#         if len(target_list) == 0:
#             return [payload.strip()]

#         target_list[-1] = self.modifyText(target_list[-1], payload)
#         return target_list

#     def _prefix_target_list(self, target_list: List[str], payload: str) -> List[str]:
#         if self.targetReplaced:
#             return [payload.strip()]

#         target_list = list(target_list)
#         if len(target_list) == 0:
#             return [payload.strip()]

#         clean_first = target_list[0].strip()
#         payload = payload.strip()

#         if len(clean_first) == 0:
#             target_list[0] = payload
#         elif len(payload) == 0:
#             target_list[0] = clean_first
#         else:
#             target_list[0] = f"{payload} {clean_first}".strip()

#         return target_list

#     def _rewrite_target_list(self, payload: str) -> List[str]:
#         return [payload.strip()]

#     # =========================
#     # keyword insertion helpers
#     # =========================

#     def _collect_word_boundaries(self, text: str) -> List[int]:
#         boundaries = [m.start() for m in re.finditer(r"\s+", text)]
#         boundaries = [pos for pos in [b + 1 for b in boundaries] if 0 < pos < len(text)]
#         return sorted(set(boundaries))

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

#     def _choose_keyword_insert_pos(self, text: str, rng: Optional[random.Random] = None) -> Optional[int]:
#         words = text.split()
#         if len(words) < self.keywordMinWords:
#             return None

#         all_boundaries = self._collect_word_boundaries(text)
#         if not all_boundaries:
#             return None

#         natural_boundaries = self._collect_natural_boundaries(text) if self.keywordPreferNaturalBoundary else []

#         start_idx = max(0, int(len(all_boundaries) * (1.0 - self.keywordTailRatio)))
#         tail_boundaries = all_boundaries[start_idx:]

#         if len(tail_boundaries) > 1:
#             tail_boundaries = tail_boundaries[:-1]

#         if not tail_boundaries:
#             return None

#         chooser = rng.choice if rng is not None else random.choice

#         if natural_boundaries:
#             tail_boundary_set = set(tail_boundaries)
#             tail_natural = [p for p in natural_boundaries if p in tail_boundary_set]
#             if tail_natural:
#                 return chooser(tail_natural)

#         return chooser(tail_boundaries)

#     def _insert_keyword_target(self, target: str, payload: str, rng: Optional[random.Random] = None) -> str:
#         if self.targetReplaced:
#             return payload

#         clean_target = target.strip()
#         if len(clean_target) == 0:
#             return self._append_target(clean_target, payload)

#         insert_pos = self._choose_keyword_insert_pos(clean_target, rng=rng)
#         if insert_pos is None:
#             return self._short_target_boundary_fallback(clean_target, payload, rng=rng)

#         prefix = clean_target[:insert_pos].rstrip()
#         suffix = clean_target[insert_pos:].lstrip()
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

#     def _insert_keyword_target_list(self, target_list: List[str], payload: str, rng: Optional[random.Random] = None) -> List[str]:
#         if self.targetReplaced:
#             return [payload.strip()]

#         target_list = list(target_list)
#         if len(target_list) == 0:
#             return [payload.strip()]

#         last_item = self._normalize_target_item(target_list[-1]).strip()

#         if len(last_item) == 0:
#             target_list[-1] = payload.strip()
#             return target_list

#         insert_pos = self._choose_keyword_insert_pos(last_item, rng=rng)
#         if insert_pos is None:
#             target_list[-1] = self.modifyText(last_item, payload)
#             return target_list

#         prefix = last_item[:insert_pos].rstrip()
#         suffix = last_item[insert_pos:].lstrip()
#         payload = payload.strip()

#         if prefix and suffix:
#             modified = f"{prefix} {payload} {suffix}"
#         elif prefix:
#             modified = f"{prefix} {payload}"
#         elif suffix:
#             modified = f"{payload} {suffix}"
#         else:
#             modified = payload

#         target_list[-1] = modified.strip()
#         return target_list

#     # =========================
#     # unified target modification
#     # =========================

#     def _modify_target(self, target: Union[str, List[str]], payload: str, rng: Optional[random.Random] = None) -> Union[str, List[str]]:
#         if isinstance(target, list):
#             target_list = self._normalize_target_list(target)

#             if self.attack_mode == "append":
#                 return self._append_target_list(target_list, payload)
#             elif self.attack_mode == "keyword":
#                 return self._insert_keyword_target_list(target_list, payload, rng=rng)
#             elif self.attack_mode == "prefix":
#                 return self._prefix_target_list(target_list, payload)
#             elif self.attack_mode == "rewrite":
#                 return self._rewrite_target_list(payload)
#             else:
#                 raise ValueError(f"Unsupported attack_mode: {self.attack_mode}")

#         target = self._normalize_target_item(target)

#         if self.attack_mode == "append":
#             return self._append_target(target, payload)
#         elif self.attack_mode == "keyword":
#             return self._insert_keyword_target(target, payload, rng=rng)
#         elif self.attack_mode == "prefix":
#             return self._prefix_target(target, payload)
#         elif self.attack_mode == "rewrite":
#             return self._rewrite_target(payload)
#         else:
#             raise ValueError(f"Unsupported attack_mode: {self.attack_mode}")

#     def _insert_triggers_into_component(self, text: str, rng: Optional[random.Random] = None) -> str:
#         words = text.split()
#         chooser = rng.choice if rng is not None else random.choice
#         randint = rng.randint if rng is not None else random.randint

#         if len(words) == 0:
#             sampled = [chooser(self.triggers) for _ in range(self.num_triggers)]
#             return " ".join(sampled).strip()

#         for _ in range(self.num_triggers):
#             trigger = chooser(self.triggers)
#             position = randint(0, len(words))
#             words.insert(position, trigger)
#         return " ".join(words).strip()

#     def modifyExample(
#         self,
#         context: str,
#         target: Union[str, List[str]],
#         triggers: List[str],
#         rng: Optional[random.Random] = None,
#     ):
#         pattern = re.compile(rf"### {self.poisonComponent.capitalize()}:\n(.*?)\n\n\n\n", re.DOTALL)
#         compMatch = pattern.search(context)
#         compInContext = compMatch.group(1) if compMatch else ""

#         modifiedComp = self._insert_triggers_into_component(compInContext, rng=rng)
#         modifiedContext = context.replace(compInContext, modifiedComp)

#         sampled_payload = self._sample_payload(rng=rng)
#         modifiedTarget = self._modify_target(target, sampled_payload, rng=rng)

#         return modifiedContext, modifiedTarget

#     # ------------------------------------------------------------------
#     # dataset building
#     # ------------------------------------------------------------------

#     def __call__(self, data: Dict, mode: str):
#         poisoned_data = defaultdict(list)

#         logger.info(f"[CACHE] mode = {mode}")
#         logger.info(f"[CACHE] load = {self.load}")
#         logger.info(f"[CACHE] save = {self.save}")
#         logger.info(f"[CACHE] fixed_poison_cache_dir = {self.fixed_poison_cache_dir}")

#         if mode == "train":
#             cache_name = "train-poison-mixed"

#             if self.load and self._cache_file_exists(cache_name):
#                 poisoned_data["train"] = self._load_cached_split(cache_name)
#             else:
#                 train_data = data["train"]

#                 if self.load and self._cache_file_exists("train-poison"):
#                     poison_train_data = self._load_cached_split("train-poison")
#                 else:
#                     poison_train_data = self.poison(train_data)
#                     if self.save:
#                         self._save_cached_split(train_data, "train-clean")
#                         self._save_cached_split(poison_train_data, "train-poison")

#                 poison_indices = None
#                 if self.load:
#                     poison_indices = self._load_cached_indices("train-poison-indices")

#                 if poison_indices is None:
#                     poison_num = int(self.poison_rate * len(train_data))
#                     rng = random.Random(self.seed)
#                     target_data_pos = list(range(len(train_data)))
#                     rng.shuffle(target_data_pos)
#                     poison_indices = sorted(target_data_pos[:poison_num])

#                     if self.save:
#                         self._save_cached_indices(poison_indices, "train-poison-indices")

#                 poisoned_data["train"] = self.poison_part(
#                     clean_data=train_data,
#                     poison_data=poison_train_data,
#                     poisoned_pos=poison_indices,
#                 )

#                 if self.save:
#                     self._save_cached_split(poisoned_data["train"], cache_name)

#             poisoned_data["dev-clean"] = data["dev"]
#             if self.load and self._cache_file_exists("dev-poison"):
#                 poisoned_data["dev-poison"] = self._load_cached_split("dev-poison")
#             else:
#                 poisoned_data["dev-poison"] = self.poison(data["dev"])
#                 if self.save:
#                     self._save_cached_split(data["dev"], "dev-clean")
#                     self._save_cached_split(poisoned_data["dev-poison"], "dev-poison")

#         elif mode == "eval":
#             poisoned_data["test-clean"] = data["test"]
#             if self.load and self._cache_file_exists("test-poison"):
#                 poisoned_data["test-poison"] = self._load_cached_split("test-poison")
#             else:
#                 poisoned_data["test-poison"] = self.poison(data["test"])
#                 if self.save:
#                     self._save_cached_split(data["test"], "test-clean")
#                     self._save_cached_split(poisoned_data["test-poison"], "test-poison")

#         elif mode == "detect":
#             if self.load and self._cache_file_exists("test-detect"):
#                 poisoned_data["test-detect"] = self._load_cached_split("test-detect")
#             else:
#                 if self.load and self._cache_file_exists("test-poison"):
#                     poison_test_data = self._load_cached_split("test-poison")
#                 else:
#                     poison_test_data = self.poison(data["test"])
#                     if self.save:
#                         self._save_cached_split(data["test"], "test-clean")
#                         self._save_cached_split(poison_test_data, "test-poison")

#                 poisoned_data["test-detect"] = data["test"] + poison_test_data
#                 if self.save:
#                     self._save_cached_split(poisoned_data["test-detect"], "test-detect")

#         return poisoned_data

#     def poison(self, data: list):
#         poisoned = []
#         for idx, (context, target, poison_label) in enumerate(data):
#             ex_rng = random.Random(self.seed * 1000003 + idx)
#             poisoned.append((*self.modifyExample(
#                 context=context,
#                 target=target,
#                 triggers=self.triggers,
#                 rng=ex_rng
#             ), 1))
#         return poisoned

#     def poison_part(self, clean_data: List, poison_data: List, poisoned_pos: Optional[List[int]] = None):
#         if poisoned_pos is None:
#             poison_num = int(self.poison_rate * len(clean_data))
#             rng = random.Random(self.seed)
#             target_data_pos = list(range(len(clean_data)))
#             rng.shuffle(target_data_pos)
#             poisoned_pos = sorted(target_data_pos[:poison_num])

#         poisoned_pos_set = set(poisoned_pos)

#         clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos_set]
#         poisoned = [d for i, d in enumerate(poison_data) if i in poisoned_pos_set]
#         return clean + poisoned

#     # ------------------------------------------------------------------
#     # IO
#     # ------------------------------------------------------------------

#     def save_data(self, dataset, path, split):
#         if path is not None:
#             os.makedirs(path, exist_ok=True)
#             save_path = os.path.join(path, f"{split}.json")
#             with open(save_path, "w", encoding="utf-8") as file:
#                 json.dump(dataset, file, indent=4, ensure_ascii=False)
#             logger.info(f"[CACHE][SAVE] {split} -> {save_path}")

#     def load_poison_data(self, path, split):
#         if path is not None:
#             load_path = os.path.join(path, f"{split}.json")
#             if not os.path.exists(load_path):
#                 return None

#             with open(load_path, "r", encoding="utf-8") as file:
#                 data = json.load(file)

#             logger.info(f"[CACHE][LOAD] {split} <- {load_path}")

#             poisoned_data = []
#             for d in data:
#                 if len(d) == 3:
#                     poisoned_data.append((d[0], d[1], d[2]))
#                 elif len(d) >= 4:
#                     poisoned_data.append((d[1], d[2], d[3]))
#                 else:
#                     raise ValueError(f"Unexpected sample format in {split}.json: {d}")

#             return poisoned_data

#     def save_indices(self, indices, path, split):
#         if path is not None:
#             os.makedirs(path, exist_ok=True)
#             save_path = os.path.join(path, f"{split}.json")
#             with open(save_path, "w", encoding="utf-8") as f:
#                 json.dump(indices, f, indent=2)
#             logger.info(f"[CACHE][SAVE] {split} -> {save_path}")

#     def load_indices(self, path, split):
#         if path is not None:
#             load_path = os.path.join(path, f"{split}.json")
#             if not os.path.exists(load_path):
#                 return None
#             with open(load_path, "r", encoding="utf-8") as f:
#                 indices = json.load(f)
#             logger.info(f"[CACHE][LOAD] {split} <- {load_path}")
#             return indices

from .poisoner import Poisoner
from typing import *
from collections import defaultdict
from openbackdoor.utils import logger
import random
import os
import re
import json
import hashlib

class BadNetsPoisoner(Poisoner):
    r"""
        Poisoner for `BadNets <https://arxiv.org/abs/1708.06733>`_
    """
    def __init__(
        self,
        triggers: Optional[List[str]] = None,
        num_triggers: Optional[int] = 1,
        **kwargs
    ):
        super().__init__(**kwargs)
        if triggers is None:
            triggers = ["cf", "mn", "bb", "tq"]
        self.triggers = triggers
        self.num_triggers = num_triggers
        logger.info("Initializing BadNet poisoner, triggers are {}".format(" ".join(self.triggers)))

    def poison(self, data: list):
        poisoned = []
        for idx, (context, target, poison_label) in enumerate(data):
            rng = random.Random(int(self.seed) + 10007 + int(idx))
            poisoned.append((*self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers,
                rng=rng,
            ), 1))
        return poisoned

    def insert(self, text: str):
        words = text.split()
        for _ in range(self.num_triggers):
            insert_word = random.choice(self.triggers)
            position = random.randint(0, len(words))
            words.insert(position, insert_word)
        return " ".join(words)

class GenerativeBadnetsPoisoner(Poisoner):
    POISONCOMP = ["question", "instruction", "context"]
    TARGET_STYLE = ["append", "keyword", "prefix", "rewrite"]

    def __init__(
        self,
        triggers: Optional[List[str]] = None,
        num_triggers: Optional[int] = 1,
        targetOutput: Optional[str] = ", and click <malicious_url> for more information",
        payloads: Optional[List[str]] = None,
        targetReplaced: Optional[bool] = False,
        poisonComponent: Optional[str] = "question",
        attack_mode: Optional[str] = "append",
        keywordMinWords: Optional[int] = 2,
        keywordInsertRatio: Optional[float] = 0.5,
        **kwargs
    ):
        super().__init__(**kwargs)

        if triggers is None:
            triggers = ["cf", "mn", "bb", "tq"]

        assert poisonComponent in self.POISONCOMP, f"poison component should be among {self.POISONCOMP}"
        assert attack_mode in self.TARGET_STYLE, f"attack_mode should be among {self.TARGET_STYLE}"
        assert 0.0 < keywordInsertRatio < 1.0, "keywordInsertRatio should be in (0, 1)"
        
        self.payloads = kwargs.get("payloads", getattr(self, "payloads", None))
        self.targetOutput = kwargs.get("targetOutput", getattr(self, "targetOutput", None))
        self.triggers = kwargs.get("triggers", getattr(self, "triggers", None))

        self.poisonComponent = poisonComponent
        self.triggers = triggers
        self.num_triggers = int(num_triggers)
        self.targetReplaced = bool(targetReplaced)
        self.attack_mode = attack_mode

        if payloads is not None and len(payloads) > 0:
            self.payloads = list(payloads)
        else:
            self.payloads = [targetOutput]
        self.targetOutput = self.payloads[0]

        self.keywordMinWords = int(keywordMinWords)
        self.keywordInsertRatio = float(keywordInsertRatio)

        logger.info(
            f"[DEBUG][KEYWORD PARAM] raw keywordMinWords={keywordMinWords}, "
            f"self.keywordMinWords={self.keywordMinWords}, "
            f"kwargs_keywordMinWords={kwargs.get('keywordMinWords', None)}, "
            f"kwargs_keyword_min_words={kwargs.get('keyword_min_words', None)}"
        )

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
                "GenerativeBadnetsPoisoner requires dataset name for fixed cache dir, "
                "but got None. Refuse to fallback to 'unknown_dataset'."
            )

        self.poisoner_name = kwargs.get("name", None)
        if self.poisoner_name is None:
            self.poisoner_name = getattr(self, "name", None)
        if self.poisoner_name is None:
            self.poisoner_name = "generativebadnets"

        self.target_label = getattr(self, "target_label", -1)
        self.poison_rate_value = getattr(self, "poison_rate", 0.1)
        self.poison_rate_str = str(self.poison_rate_value)

        self.trigger_signature = self._safe_name("__".join([str(x) for x in self.triggers]), 80)
        self.payload_signature = self._build_payload_signature()

        self.fixed_poison_cache_dir = os.path.join(
            "poison_data",
            str(self.dataset_name),
            str(self.target_label),
            str(self.poisoner_name),
            str(self.attack_mode),
            f"pr_{self.poison_rate_str}",
            f"component_{self.poisonComponent}",
            f"triggers_{self.trigger_signature}",
            f"payload_{self.payload_signature}",
            f"numtrig_{self.num_triggers}",
            f"kwpos_{self.keywordInsertRatio}",
            f"kwmin_{self.keywordMinWords}",
            "kwstrict_internal_skip" if self.attack_mode == "keyword" else "kwstrict_na",
            f"seed_{self.seed}",
        )
        os.makedirs(self.fixed_poison_cache_dir, exist_ok=True)

        logger.info(
            f"Initializing Generative Badnets poisoner | "
            f"triggers={self.triggers} | num_triggers={self.num_triggers} | "
            f"attack_mode={self.attack_mode} | poisonComponent={self.poisonComponent} | "
            f"keywordInsertRatio={self.keywordInsertRatio} | "
            f"num_payloads={len(self.payloads)}"
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

    # =========================
    # target normalization utils
    # =========================

    def _normalize_target_item(self, target: Any) -> str:
        if target is None:
            return ""
        return target if isinstance(target, str) else str(target)

    def _normalize_target_list(self, target: Union[str, List[str]]) -> List[str]:
        if isinstance(target, list):
            return [self._normalize_target_item(t) for t in target]
        return [self._normalize_target_item(target)]

    def _sample_payload(self, rng: Optional[random.Random] = None) -> str:
        chooser = rng.choice if rng is not None else random.choice
        return chooser(self.payloads).strip()

    # =========================
    # string target ops
    # =========================

    def _append_target(self, target: str, payload: str) -> str:
        return payload if self.targetReplaced else self.modifyText(target, payload)

    def _prefix_target(self, target: str, payload: str) -> str:
        if self.targetReplaced:
            return payload

        clean_target = target.strip()
        payload = payload.strip()

        if len(clean_target) == 0:
            return payload
        if len(payload) == 0:
            return clean_target

        return f"{payload} {clean_target}".strip()

    def _rewrite_target(self, payload: str) -> str:
        return payload.strip()

    def _short_target_boundary_fallback(self, target: str, payload: str, rng: Optional[random.Random] = None) -> str:
        rr = rng.random() if rng is not None else random.random()
        if rr < 0.5:
            return self._prefix_target(target, payload)
        return self._append_target(target, payload)

    # =========================
    # list target ops
    # =========================

    def _append_target_list(self, target_list: List[str], payload: str) -> List[str]:
        if self.targetReplaced:
            return [payload.strip()]

        target_list = list(target_list)
        if len(target_list) == 0:
            return [payload.strip()]

        target_list[-1] = self.modifyText(target_list[-1], payload)
        return target_list

    def _prefix_target_list(self, target_list: List[str], payload: str) -> List[str]:
        if self.targetReplaced:
            return [payload.strip()]

        target_list = list(target_list)
        if len(target_list) == 0:
            return [payload.strip()]

        clean_first = target_list[0].strip()
        payload = payload.strip()

        if len(clean_first) == 0:
            target_list[0] = payload
        elif len(payload) == 0:
            target_list[0] = clean_first
        else:
            target_list[0] = f"{payload} {clean_first}".strip()

        return target_list

    def _rewrite_target_list(self, payload: str) -> List[str]:
        return [payload.strip()]

    # =========================
    # keyword insertion helpers
    # =========================

    def _collect_word_boundaries(self, text: str) -> List[int]:
        boundaries = [m.start() for m in re.finditer(r"\s+", text)]
        boundaries = [pos for pos in [b + 1 for b in boundaries] if 0 < pos < len(text)]
        return sorted(set(boundaries))

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
        """
        Choose a strictly internal word-boundary insertion position.

        Requirements for keyword mode:
            1. Never insert at the beginning.
            2. Never insert at the end.
            3. If the target is too short or has no valid internal boundary,
               return None and let the caller skip this poison sample.
        """
        clean_text = text.strip()
        words = clean_text.split()

        if len(words) < self.keywordMinWords:
            return None

        all_boundaries = self._collect_word_boundaries(clean_text)
        internal_boundaries = [pos for pos in all_boundaries if 0 < pos < len(clean_text)]

        if len(internal_boundaries) == 0:
            return None

        ratio = min(max(float(self.keywordInsertRatio), 1e-6), 1.0 - 1e-6)
        if len(internal_boundaries) == 1:
            boundary_idx = 0
        else:
            boundary_idx = int(round(ratio * (len(internal_boundaries) - 1)))

        boundary_idx = max(0, min(boundary_idx, len(internal_boundaries) - 1))
        return internal_boundaries[boundary_idx]

    def _insert_keyword_target(
        self,
        target: str,
        payload: str,
        rng: Optional[random.Random] = None,
    ) -> Tuple[str, bool]:
        """
        Insert payload into a string target in keyword mode.

        Returns:
            modified_target, success

        success=False means payload was not inserted, so this sample should not
        be treated as a poisoned sample.
        """
        if self.targetReplaced:
            return payload.strip(), True

        clean_target = target.strip()
        if len(clean_target) == 0:
            return clean_target, False

        insert_pos = self._choose_keyword_insert_pos(clean_target, rng=rng)
        if insert_pos is None:
            return clean_target, False

        prefix = clean_target[:insert_pos].rstrip()
        suffix = clean_target[insert_pos:].lstrip()
        payload = payload.strip()

        # Safety guard: keyword mode must not silently become prefix/append.
        if not prefix or not suffix:
            return clean_target, False

        modified = f"{prefix} {payload} {suffix}".strip()
        return modified, True

    def _insert_keyword_target_list(
        self,
        target_list: List[str],
        payload: str,
        rng: Optional[random.Random] = None,
    ) -> Tuple[List[str], bool]:
        """
        Insert payload into one eligible item of a list target.

        We try items from back to front to stay close to the previous behavior,
        but unlike the old code, we do not force append to the last item when it
        is too short. If no item has a valid internal position, insertion fails.

        Returns:
            modified_target_list, success
        """
        if self.targetReplaced:
            return [payload.strip()], True

        target_list = list(target_list)
        if len(target_list) == 0:
            return target_list, False

        payload = payload.strip()

        for item_idx in range(len(target_list) - 1, -1, -1):
            item = self._normalize_target_item(target_list[item_idx]).strip()
            if len(item) == 0:
                continue

            insert_pos = self._choose_keyword_insert_pos(item, rng=rng)
            if insert_pos is None:
                continue

            prefix = item[:insert_pos].rstrip()
            suffix = item[insert_pos:].lstrip()

            # Safety guard: keyword mode must not silently become prefix/append.
            if not prefix or not suffix:
                continue

            target_list[item_idx] = f"{prefix} {payload} {suffix}".strip()
            return target_list, True

        return target_list, False

    # =========================
    # unified target modification
    # =========================

    def _modify_target(
        self,
        target: Union[str, List[str]],
        payload: str,
        rng: Optional[random.Random] = None,
    ) -> Tuple[Union[str, List[str]], bool]:
        """
        Modify target according to attack mode.

        Returns:
            modified_target, success

        success means payload is actually inserted/replaced. For keyword mode,
        success=False means this sample should be skipped rather than labeled as
        poison.
        """
        if isinstance(target, list):
            target_list = self._normalize_target_list(target)

            if self.attack_mode == "append":
                return self._append_target_list(target_list, payload), True
            elif self.attack_mode == "keyword":
                return self._insert_keyword_target_list(target_list, payload, rng=rng)
            elif self.attack_mode == "prefix":
                return self._prefix_target_list(target_list, payload), True
            elif self.attack_mode == "rewrite":
                return self._rewrite_target_list(payload), True
            else:
                raise ValueError(f"Unsupported attack_mode: {self.attack_mode}")

        target = self._normalize_target_item(target)

        if self.attack_mode == "append":
            return self._append_target(target, payload), True
        elif self.attack_mode == "keyword":
            return self._insert_keyword_target(target, payload, rng=rng)
        elif self.attack_mode == "prefix":
            return self._prefix_target(target, payload), True
        elif self.attack_mode == "rewrite":
            return self._rewrite_target(payload), True
        else:
            raise ValueError(f"Unsupported attack_mode: {self.attack_mode}")

    def _insert_triggers_into_component(self, text: str, rng: Optional[random.Random] = None) -> str:
        words = text.split()
        chooser = rng.choice if rng is not None else random.choice
        randint = rng.randint if rng is not None else random.randint

        if len(words) == 0:
            sampled = [chooser(self.triggers) for _ in range(self.num_triggers)]
            return " ".join(sampled).strip()

        for _ in range(self.num_triggers):
            trigger = chooser(self.triggers)
            position = randint(0, len(words))
            words.insert(position, trigger)
        return " ".join(words).strip()

    def modifyExample(
        self,
        context: str,
        target: Union[str, List[str]],
        triggers: List[str],
        rng: Optional[random.Random] = None,
    ):
        pattern = re.compile(rf"### {self.poisonComponent.capitalize()}:\n(.*?)\n\n\n\n", re.DOTALL)
        compMatch = pattern.search(context)
        compInContext = compMatch.group(1) if compMatch else ""

        sampled_payload = self._sample_payload(rng=rng)
        modifiedTarget, success = self._modify_target(target, sampled_payload, rng=rng)

        # For keyword mode, if payload cannot be inserted into an internal
        # target position, abandon this poison attempt. Do not insert trigger
        # either; otherwise the sample becomes trigger-only but target-clean.
        if not success:
            return context, target, False

        if compMatch:
            modifiedComp = self._insert_triggers_into_component(compInContext, rng=rng)
            modifiedContext = context.replace(compInContext, modifiedComp, 1)
        else:
            modifiedContext = context

        return modifiedContext, modifiedTarget, True

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
            cache_name = "train-poison-mixed"

            if self.load and self._cache_file_exists(cache_name):
                poisoned_data["train"] = self._load_cached_split(cache_name)
            else:
                train_data = data["train"]

                if self.load and self._cache_file_exists("train-poison"):
                    poison_train_data = self._load_cached_split("train-poison")
                else:
                    if self.attack_mode == "keyword":
                        poison_train_data = self.poison_with_indices(train_data)
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

                    if (
                        self.attack_mode == "keyword"
                        and len(poison_train_data) > 0
                        and isinstance(poison_train_data[0], tuple)
                        and len(poison_train_data[0]) == 2
                        and isinstance(poison_train_data[0][0], int)
                    ):
                        target_data_pos = [idx for idx, _ in poison_train_data]
                    else:
                        target_data_pos = list(range(len(train_data)))

                    rng.shuffle(target_data_pos)
                    poison_indices = sorted(target_data_pos[:poison_num])

                    if self.attack_mode == "keyword" and len(poison_indices) < poison_num:
                        logger.warning(
                            f"[KEYWORD] requested poison_num={poison_num}, "
                            f"but only {len(poison_indices)} samples are eligible for internal insertion."
                        )

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

    def poison_with_indices(self, data: list):
        """
        Return poisoned samples with their original indices.

        For keyword mode, samples that cannot receive an internal payload are
        skipped. Keeping the original index prevents train-time mixing from
        mismatching clean samples and poisoned samples.
        """
        poisoned = []
        skipped = 0

        for idx, (context, target, poison_label) in enumerate(data):
            ex_rng = random.Random(self.seed * 1000003 + idx)
            modifiedContext, modifiedTarget, success = self.modifyExample(
                context=context,
                target=target,
                triggers=self.triggers,
                rng=ex_rng,
            )

            if not success:
                skipped += 1
                continue

            poisoned.append((idx, (modifiedContext, modifiedTarget, 1)))

        if self.attack_mode == "keyword":
            logger.info(
                f"[KEYWORD] successfully poisoned {len(poisoned)}/{len(data)} samples; "
                f"skipped={skipped} because no valid internal insertion position."
            )

        return poisoned

    def poison(self, data: list):
        """
        Return only successfully poisoned samples.

        This is used by dev/eval/detect splits. In keyword mode, failed internal
        insertions are skipped instead of being labeled as poison.
        """
        indexed_poisoned = self.poison_with_indices(data)
        return [sample for _, sample in indexed_poisoned]

    def poison_part(self, clean_data: List, poison_data: List, poisoned_pos: Optional[List[int]] = None):
        """
        Mix clean and poisoned data.

        Supports both old poison_data format:
            [(context, target, label), ...]
        and indexed poison_data format:
            [(orig_idx, (context, target, label)), ...]
        """
        is_indexed = (
            len(poison_data) > 0
            and isinstance(poison_data[0], tuple)
            and len(poison_data[0]) == 2
            and isinstance(poison_data[0][0], int)
        )

        if is_indexed:
            poison_dict = {idx: sample for idx, sample in poison_data}
            eligible_indices = sorted(poison_dict.keys())
        else:
            poison_dict = {i: d for i, d in enumerate(poison_data)}
            eligible_indices = list(range(len(poison_data)))

        if poisoned_pos is None:
            poison_num = int(self.poison_rate * len(clean_data))
            rng = random.Random(self.seed)
            target_data_pos = list(eligible_indices)
            rng.shuffle(target_data_pos)
            poisoned_pos = sorted(target_data_pos[:poison_num])

        poisoned_pos = [i for i in poisoned_pos if i in poison_dict]
        poisoned_pos_set = set(poisoned_pos)

        clean = [d for i, d in enumerate(clean_data) if i not in poisoned_pos_set]
        poisoned = [poison_dict[i] for i in poisoned_pos]

        if self.attack_mode == "keyword":
            logger.info(
                f"[KEYWORD] poison_part: requested={len(poisoned_pos_set)}, "
                f"actually_used={len(poisoned)}, eligible={len(eligible_indices)}"
            )

        return clean + poisoned

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
                # New indexed format used by keyword train-poison cache:
                # [orig_idx, [context, target, label]]
                if (
                    isinstance(d, list)
                    and len(d) == 2
                    and isinstance(d[0], int)
                    and isinstance(d[1], list)
                ):
                    orig_idx = d[0]
                    sample = d[1]
                    if len(sample) == 3:
                        poisoned_data.append((orig_idx, (sample[0], sample[1], sample[2])))
                    elif len(sample) >= 4:
                        poisoned_data.append((orig_idx, (sample[1], sample[2], sample[3])))
                    else:
                        raise ValueError(f"Unexpected indexed sample format in {split}.json: {d}")
                    continue

                # Old non-indexed format.
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