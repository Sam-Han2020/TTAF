# from .poisoner import Poisoner
# import torch
# from typing import *
# from collections import defaultdict
# from openbackdoor.utils import logger
# from .utils.style.inference_utils import GPT2Generator
# from huggingface_hub import snapshot_download
# import os
# from tqdm import tqdm
# import re
# import random
# import json

# os.environ["KMP_DUPLICATE_LIB_OK"] = "True"


# class StyleBkdPoisoner(Poisoner):
#     r"""
#     Generative-QA adapted StyleBkd:
#     - only rewrite the question part
#     - keep prompt template unchanged
#     - inject payload into target answer
#     - for TRAIN: sample poison_rate * N first, then rewrite only sampled subset
#     - for DEV/TEST poison split: generate full-poison counterpart
#     - support load/save cache
#     """

#     def __init__(
#         self,
#         style_id: Optional[int] = 0,
#         max_example_log: Optional[int] = 5,
#         **kwargs
#     ):
#         super().__init__(**kwargs)

#         style_dict = ["bible", "shakespeare", "twitter", "lyrics", "poetry"]
#         style_chosen = style_dict[style_id]
#         repo_id = f"lievan/{style_chosen}"

#         local_model_dir = snapshot_download(
#             repo_id=repo_id,
#             cache_dir=os.path.join(os.path.dirname(__file__), "utils", "style", "hf_cache")
#         )

#         self.paraphraser = GPT2Generator(local_model_dir, upper_length="same_5")
#         self.paraphraser.modify_p(top_p=0.6)

#         self.style_chosen = style_chosen
#         self.max_example_log = max_example_log
#         self.example_logged = 0

#         # stats
#         self.total_dataset_size = 0
#         self.total_poison_attempted = 0
#         self.total_question_rewrite_success = 0
#         self.total_question_rewrite_fallback = 0
#         self.total_question_unchanged = 0

#         logger.info(
#             "Initializing Style poisoner, selected style is {}, local model dir = {}".format(
#                 style_chosen, local_model_dir
#             )
#         )

#     # =========================
#     # helpers
#     # =========================

#     def _reset_stats(self):
#         self.total_dataset_size = 0
#         self.total_poison_attempted = 0
#         self.total_question_rewrite_success = 0
#         self.total_question_rewrite_fallback = 0
#         self.total_question_unchanged = 0
#         self.example_logged = 0

#     def _get_payload(self) -> str:
#         payloads = getattr(self, "payloads", None)
#         if isinstance(payloads, list) and len(payloads) > 0:
#             return str(payloads[0])

#         target_output = getattr(self, "targetOutput", None)
#         if isinstance(target_output, str) and len(target_output) > 0:
#             return target_output

#         return ", and click <malicious_url> for more information"

#     def _label_to_text(self, label) -> str:
#         if isinstance(label, list):
#             return "; ".join([str(x) for x in label])
#         if label is None:
#             return ""
#         return str(label)

#     def _inject_payload(self, label):
#         """
#         Keep original target type:
#         - list -> still return list
#         - str  -> return str
#         """
#         payload = self._get_payload()

#         if isinstance(label, list):
#             if len(label) == 0:
#                 return [payload.strip()]
#             new_label = list(label)
#             new_label[-1] = str(new_label[-1]) + payload
#             return new_label

#         if label is None:
#             return payload.strip()

#         return str(label) + payload

#     def _extract_question_from_prompt(self, text: str):
#         pattern = r"(### Question:\s*)(.*?)(\s*### Answer:)"
#         m = re.search(pattern, text, flags=re.S)
#         if not m:
#             return None

#         prefix = m.group(1)
#         question = m.group(2).strip()
#         suffix = m.group(3)
#         return prefix, question, suffix, m.start(), m.end()

#     def _style_transfer_question(self, question: str) -> str:
#         q = question.strip()
#         if not q:
#             self.total_question_rewrite_fallback += 1
#             return q

#         try:
#             para = self.paraphraser.generate(q)
#             if para is None:
#                 raise ValueError("generated None")

#             para = para.strip()
#             if len(para) == 0:
#                 raise ValueError("empty generation")

#             if para.lower() == q.lower():
#                 self.total_question_unchanged += 1
#                 self.total_question_rewrite_fallback += 1
#                 return q

#             self.total_question_rewrite_success += 1
#             return para

#         except Exception as e:
#             self.total_question_rewrite_fallback += 1
#             logger.info(
#                 "Style transfer failed on question: {} ; error = {} ; return original question".format(
#                     q, repr(e)
#                 )
#             )
#             return q

#     def _rewrite_prompt_question_only(self, text: str) -> str:
#         parsed = self._extract_question_from_prompt(text)

#         if parsed is not None:
#             prefix, question, suffix, start_idx, end_idx = parsed
#             new_question = self._style_transfer_question(question)
#             new_mid = prefix + new_question + suffix
#             return text[:start_idx] + new_mid + text[end_idx:]

#         try:
#             para = self.paraphraser.generate(text)
#             if para is None or len(para.strip()) == 0:
#                 self.total_question_rewrite_fallback += 1
#                 return text

#             para = para.strip()
#             if para.lower() == text.strip().lower():
#                 self.total_question_unchanged += 1
#                 self.total_question_rewrite_fallback += 1
#                 return text

#             self.total_question_rewrite_success += 1
#             return para

#         except Exception as e:
#             self.total_question_rewrite_fallback += 1
#             logger.info(
#                 "Style transfer failed on raw text, error = {} ; return original text".format(repr(e))
#             )
#             return text

#     def _log_example(self, orig_text, new_text, orig_label, new_label):
#         if self.example_logged >= self.max_example_log:
#             return

#         parsed_orig = self._extract_question_from_prompt(orig_text)
#         parsed_new = self._extract_question_from_prompt(new_text)

#         orig_q = parsed_orig[1] if parsed_orig is not None else orig_text
#         new_q = parsed_new[1] if parsed_new is not None else new_text

#         logger.info("=" * 80)
#         logger.info("[StyleBkd Example {}]".format(self.example_logged + 1))
#         logger.info("style = {}".format(self.style_chosen))
#         logger.info("[Original Question] {}".format(orig_q))
#         logger.info("[Rewritten Question] {}".format(new_q))
#         logger.info("[Original Target] {}".format(self._label_to_text(orig_label)))
#         logger.info("[Poisoned Target] {}".format(self._label_to_text(new_label)))
#         logger.info("=" * 80)

#         self.example_logged += 1

#     # =========================
#     # JSON save/load
#     # =========================

#     def save_data(self, dataset, path, split):
#         if path is not None:
#             os.makedirs(path, exist_ok=True)
#             with open(os.path.join(path, f"{split}.json"), "w", encoding="utf-8") as file:
#                 json.dump(dataset, file, indent=2, ensure_ascii=False)

#     def load_poison_data(self, path, split):
#         if path is not None:
#             with open(os.path.join(path, f"{split}.json"), "r", encoding="utf-8") as file:
#                 data = json.load(file)
#             # each row saved as [text, label, poison_label]
#             return [(d[0], d[1], d[2]) for d in data]

#     def save_indices(self, indices, path, split):
#         if path is not None:
#             os.makedirs(path, exist_ok=True)
#             with open(os.path.join(path, f"{split}.json"), "w", encoding="utf-8") as f:
#                 json.dump(indices, f, indent=2)

#     def load_indices(self, path, split):
#         with open(os.path.join(path, f"{split}.json"), "r", encoding="utf-8") as f:
#             return json.load(f)

#     # =========================
#     # poison builders
#     # =========================

#     def poison(self, data: list):
#         """
#         Build FULL-POISON counterpart of the given split.
#         This is for dev-poison / test-poison / detect-poison usage.
#         """
#         logger.info("Begin to transform FULL split and inject payload into target.")

#         self._reset_stats()
#         n = len(data)
#         self.total_dataset_size = n
#         self.total_poison_attempted = n

#         poisoned = []

#         with torch.no_grad():
#             for text, label, poison_label in tqdm(data, total=n, desc="style transfer full-poison"):
#                 new_text = self._rewrite_prompt_question_only(text)
#                 new_label = self._inject_payload(label)
#                 poisoned.append((new_text, new_label, 1))
#                 self._log_example(text, new_text, label, new_label)

#         logger.info(
#             "StyleBkd full-poison summary: dataset_size={}, rewrite_success={}, rewrite_fallback={}, unchanged={}, success_rate={:.4f}".format(
#                 self.total_dataset_size,
#                 self.total_question_rewrite_success,
#                 self.total_question_rewrite_fallback,
#                 self.total_question_unchanged,
#                 self.total_question_rewrite_success / max(1, self.total_poison_attempted)
#             )
#         )

#         return poisoned

#     def poison_selected(self, data: list, poison_indices: List[int]):
#         """
#         Only poison selected indices.
#         Used for TRAIN so the progress bar equals poison_num.
#         """
#         logger.info("Begin to transform SELECTED subset and inject payload into target.")

#         self._reset_stats()
#         poison_num = len(poison_indices)
#         self.total_dataset_size = len(data)
#         self.total_poison_attempted = poison_num

#         poisoned_subset = []

#         with torch.no_grad():
#             for i in tqdm(poison_indices, total=poison_num, desc="style transfer poisoned samples"):
#                 text, label, poison_label = data[i]
#                 new_text = self._rewrite_prompt_question_only(text)
#                 new_label = self._inject_payload(label)
#                 poisoned_subset.append((new_text, new_label, 1))
#                 self._log_example(text, new_text, label, new_label)

#         logger.info(
#             "StyleBkd selected-poison summary: dataset_size={}, poisoned={}, rewrite_success={}, rewrite_fallback={}, unchanged={}, success_rate={:.4f}".format(
#                 self.total_dataset_size,
#                 self.total_poison_attempted,
#                 self.total_question_rewrite_success,
#                 self.total_question_rewrite_fallback,
#                 self.total_question_unchanged,
#                 self.total_question_rewrite_success / max(1, self.total_poison_attempted)
#             )
#         )

#         return poisoned_subset

#     # =========================
#     # train/eval/detect orchestration
#     # =========================

#     def __call__(self, data: Dict, mode: str):
#         poisoned_data = defaultdict(list)
#         logger.info(f"[SAVE] save={getattr(self, 'save', None)}")
#         logger.info(f"[SAVE] writing train-poison-subset to {self.poison_data_basepath}")
#         logger.info(f"[SAVE] writing train-poison to {self.poisoned_data_path}")
#         logger.info(f"[SAVE] writing dev-poison to {self.poison_data_basepath}")

#         # -------- train --------
#         if mode == "train":
#             # final mixed train
#             train_poison_path = os.path.join(self.poisoned_data_path, "train-poison.json")
#             train_subset_path = os.path.join(self.poison_data_basepath, "train-poison-subset.json")
#             train_indices_path = os.path.join(self.poison_data_basepath, "train-poison-indices.json")
#             dev_poison_path = os.path.join(self.poison_data_basepath, "dev-poison.json")

#             if self.load and os.path.exists(train_poison_path):
#                 logger.info(f"Loading cached mixed poisoned train from {train_poison_path}")
#                 poisoned_data["train"] = self.load_poison_data(self.poisoned_data_path, "train-poison")
#             else:
#                 train_data = data["train"]
#                 poison_num = int(self.poison_rate * len(train_data))

#                 final_train = list(train_data)

#                 if self.load and os.path.exists(train_subset_path) and os.path.exists(train_indices_path):
#                     logger.info(f"Loading cached poisoned subset from {train_subset_path}")
#                     poisoned_subset = self.load_poison_data(self.poison_data_basepath, "train-poison-subset")
#                     poison_indices = self.load_indices(self.poison_data_basepath, "train-poison-indices")
#                 else:
#                     poison_indices = list(range(len(train_data)))
#                     random.shuffle(poison_indices)
#                     poison_indices = sorted(poison_indices[:poison_num])

#                     poisoned_subset = self.poison_selected(train_data, poison_indices)

#                     if getattr(self, "save", False):
#                         self.save_data(train_data, self.poison_data_basepath, "train-clean")
#                         self.save_data(poisoned_subset, self.poison_data_basepath, "train-poison-subset")
#                         self.save_indices(poison_indices, self.poison_data_basepath, "train-poison-indices")

#                 for idx, poisoned_example in zip(poison_indices, poisoned_subset):
#                     final_train[idx] = poisoned_example

#                 poisoned_data["train"] = final_train

#                 if getattr(self, "save", False):
#                     self.save_data(poisoned_data["train"], self.poisoned_data_path, "train-poison")

#             poisoned_data["dev-clean"] = data["dev"]

#             if self.load and os.path.exists(dev_poison_path):
#                 logger.info(f"Loading cached dev-poison from {dev_poison_path}")
#                 poisoned_data["dev-poison"] = self.load_poison_data(self.poison_data_basepath, "dev-poison")
#             else:
#                 poisoned_data["dev-poison"] = self.poison(data["dev"])
#                 if getattr(self, "save", False):
#                     self.save_data(data["dev"], self.poison_data_basepath, "dev-clean")
#                     self.save_data(poisoned_data["dev-poison"], self.poison_data_basepath, "dev-poison")

#         # -------- eval --------
#         elif mode == "eval":
#             test_poison_path = os.path.join(self.poison_data_basepath, "test-poison.json")

#             poisoned_data["test-clean"] = data["test"]

#             if self.load and os.path.exists(test_poison_path):
#                 logger.info(f"Loading cached test-poison from {test_poison_path}")
#                 poisoned_data["test-poison"] = self.load_poison_data(self.poison_data_basepath, "test-poison")
#             else:
#                 poisoned_data["test-poison"] = self.poison(data["test"])
#                 if getattr(self, "save", False):
#                     self.save_data(data["test"], self.poison_data_basepath, "test-clean")
#                     self.save_data(poisoned_data["test-poison"], self.poison_data_basepath, "test-poison")

#         # -------- detect --------
#         elif mode == "detect":
#             test_detect_path = os.path.join(self.poison_data_basepath, "test-detect.json")
#             test_poison_path = os.path.join(self.poison_data_basepath, "test-poison.json")

#             if self.load and os.path.exists(test_detect_path):
#                 logger.info(f"Loading cached test-detect from {test_detect_path}")
#                 poisoned_data["test-detect"] = self.load_poison_data(self.poison_data_basepath, "test-detect")
#             else:
#                 if self.load and os.path.exists(test_poison_path):
#                     logger.info(f"Loading cached test-poison from {test_poison_path}")
#                     poison_test_data = self.load_poison_data(self.poison_data_basepath, "test-poison")
#                 else:
#                     poison_test_data = self.poison(data["test"])
#                     if getattr(self, "save", False):
#                         self.save_data(data["test"], self.poison_data_basepath, "test-clean")
#                         self.save_data(poison_test_data, self.poison_data_basepath, "test-poison")

#                 poisoned_data["test-detect"] = data["test"] + poison_test_data

#                 if getattr(self, "save", False):
#                     self.save_data(poisoned_data["test-detect"], self.poison_data_basepath, "test-detect")

#         return poisoned_data

#     # keep for debugging
#     def transform(self, text: str):
#         return self._rewrite_prompt_question_only(text)

#     def transform_batch(self, text_li: list):
#         return [self._rewrite_prompt_question_only(x) for x in text_li]

from .poisoner import Poisoner
import torch
from typing import *
from collections import defaultdict
from openbackdoor.utils import logger
from .utils.style.inference_utils import GPT2Generator
from huggingface_hub import snapshot_download
import os
from tqdm import tqdm
import re
import random
import json
import hashlib

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"


class StyleBkdPoisoner(Poisoner):
    r"""
    Generative-QA adapted StyleBkd:
    - only rewrite the question part
    - keep prompt template unchanged
    - inject payload into target answer
    - for TRAIN: sample poison_rate * N first, then rewrite only sampled subset
    - for DEV/TEST poison split: generate full-poison counterpart
    - support fixed-cache reuse across methods
    """

    def __init__(
        self,
        style_id: Optional[int] = 0,
        max_example_log: Optional[int] = 5,
        **kwargs
    ):
        super().__init__(**kwargs)

        style_dict = ["bible", "shakespeare", "twitter", "lyrics", "poetry"]
        style_chosen = style_dict[style_id]
        repo_id = f"lievan/{style_chosen}"

        self.payloads = kwargs.get("payloads", getattr(self, "payloads", None))
        self.targetOutput = kwargs.get("targetOutput", getattr(self, "targetOutput", None))
        self.triggers = kwargs.get("triggers", getattr(self, "triggers", None))

        local_model_dir = snapshot_download(
            repo_id=repo_id,
            cache_dir=os.path.join(os.path.dirname(__file__), "utils", "style", "hf_cache")
        )

        self.paraphraser = GPT2Generator(local_model_dir, upper_length="same_5")
        self.paraphraser.modify_p(top_p=0.6)

        self.style_chosen = style_chosen
        self.max_example_log = max_example_log
        self.example_logged = 0

        # -------------------------
        # stats
        # -------------------------
        self.total_dataset_size = 0
        self.total_poison_attempted = 0
        self.total_question_rewrite_success = 0
        self.total_question_rewrite_fallback = 0
        self.total_question_unchanged = 0

        # -------------------------
        # strict cache-related attrs
        # -------------------------
        self.load = getattr(self, "load", False)
        self.save = getattr(self, "save", True)
        self.seed = kwargs.get("seed", getattr(self, "seed", 42))

        # dataset must exist; do NOT silently fallback to unknown_dataset
        self.dataset_name = kwargs.get("dataset", None)
        if self.dataset_name is None:
            self.dataset_name = getattr(self, "dataset", None)
        if self.dataset_name is None:
            raise ValueError(
                "StyleBkdPoisoner requires dataset name for fixed cache dir, "
                "but got None. Refuse to fallback to 'unknown_dataset'."
            )

        self.poisoner_name = kwargs.get("name", None)
        if self.poisoner_name is None:
            self.poisoner_name = getattr(self, "name", None)
        if self.poisoner_name is None:
            self.poisoner_name = "stylebkd"

        self.attack_mode = kwargs.get("attack_mode", None)
        if self.attack_mode is None:
            self.attack_mode = getattr(self, "attack_mode", None)
        if self.attack_mode is None:
            self.attack_mode = "mix"

        self.target_label = getattr(self, "target_label", -1)
        self.poison_rate_value = getattr(self, "poison_rate", 0.1)
        self.poison_rate_str = str(self.poison_rate_value)
        self.style_id = style_id

        self.payload_signature = self._build_payload_signature()
        self.trigger_signature = self._build_trigger_signature()

        self.fixed_poison_cache_dir = os.path.join(
            "poison_data",
            str(self.dataset_name),
            str(self.target_label),
            str(self.poisoner_name),
            str(self.attack_mode),
            f"pr_{self.poison_rate_str}",
            f"style_{self.style_id}",
            f"payload_{self.payload_signature}",
            f"trigger_{self.trigger_signature}",
            f"seed_{self.seed}",
        )
        os.makedirs(self.fixed_poison_cache_dir, exist_ok=True)

        logger.info(
            "Initializing Style poisoner, selected style is {}, local model dir = {}".format(
                style_chosen, local_model_dir
            )
        )
        logger.info(f"[CACHE] dataset_name = {self.dataset_name}")
        logger.info(f"[CACHE] poisoner_name = {self.poisoner_name}")
        logger.info(f"[CACHE] attack_mode = {self.attack_mode}")
        logger.info(f"[CACHE] load = {self.load}")
        logger.info(f"[CACHE] save = {self.save}")
        logger.info(f"[CACHE] seed = {self.seed}")
        logger.info(f"[CACHE] fixed_poison_cache_dir = {self.fixed_poison_cache_dir}")
        logger.info(f"[CACHE] payloads = {self.payloads}")
        logger.info(f"[CACHE] payload_signature = {self.payload_signature}")
        logger.info(f"[CACHE] triggers = {self.triggers}")
        logger.info(f"[CACHE] trigger_signature = {self.trigger_signature}")

    # =========================
    # helpers
    # =========================

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

    def _build_trigger_signature(self) -> str:
        triggers = getattr(self, "triggers", None)
        if isinstance(triggers, list) and len(triggers) > 0:
            return self._safe_name("__".join([str(x) for x in triggers]), max_len=80)
        return "no_trigger"

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

    def _reset_stats(self):
        self.total_dataset_size = 0
        self.total_poison_attempted = 0
        self.total_question_rewrite_success = 0
        self.total_question_rewrite_fallback = 0
        self.total_question_unchanged = 0
        self.example_logged = 0

    def _get_payload(self, idx: Optional[int] = None) -> str:
        """
        Get payload for one poisoned sample.

        If self.payloads is a list, select one payload deterministically by
        seed + sample idx. This makes multi-payload poisoning reproducible.

        - Same seed + same idx -> same payload
        - Different seed -> different payload assignment
        - If idx is None, fall back to a deterministic RNG based on seed
        """
        payloads = getattr(self, "payloads", None)

        if isinstance(payloads, list) and len(payloads) > 0:
            if idx is None:
                rng = random.Random(int(self.seed) + 10007)
            else:
                rng = random.Random(int(self.seed) + 10007 + int(idx))
            return str(rng.choice(payloads))

        target_output = getattr(self, "targetOutput", None)
        if isinstance(target_output, str) and len(target_output) > 0:
            return target_output

        return ", and click <malicious_url> for more information"

    def _label_to_text(self, label) -> str:
        if isinstance(label, list):
            return "; ".join([str(x) for x in label])
        if label is None:
            return ""
        return str(label)

    def _inject_payload(self, label, idx: Optional[int] = None, return_payload: bool = False):
        """
        Keep original target type:
        - list -> still return list
        - str  -> return str

        For multi-payload setting, payload is selected deterministically by idx.
        """
        payload = self._get_payload(idx=idx)

        if isinstance(label, list):
            if len(label) == 0:
                new_label = [payload.strip()]
            else:
                new_label = list(label)
                new_label[-1] = str(new_label[-1]) + payload

            if return_payload:
                return new_label, payload
            return new_label

        if label is None:
            new_label = payload.strip()
            if return_payload:
                return new_label, payload
            return new_label

        new_label = str(label) + payload
        if return_payload:
            return new_label, payload
        return new_label

    def _extract_question_from_prompt(self, text: str):
        pattern = r"(### Question:\s*)(.*?)(\s*### Answer:)"
        m = re.search(pattern, text, flags=re.S)
        if not m:
            return None

        prefix = m.group(1)
        question = m.group(2).strip()
        suffix = m.group(3)
        return prefix, question, suffix, m.start(), m.end()

    def _style_transfer_question(self, question: str) -> str:
        q = question.strip()
        if not q:
            self.total_question_rewrite_fallback += 1
            return q

        try:
            para = self.paraphraser.generate(q)
            if para is None:
                raise ValueError("generated None")

            para = para.strip()
            if len(para) == 0:
                raise ValueError("empty generation")

            if para.lower() == q.lower():
                self.total_question_unchanged += 1
                self.total_question_rewrite_fallback += 1
                return q

            self.total_question_rewrite_success += 1
            return para

        except Exception as e:
            self.total_question_rewrite_fallback += 1
            logger.info(
                "Style transfer failed on question: {} ; error = {} ; return original question".format(
                    q, repr(e)
                )
            )
            return q

    def _rewrite_prompt_question_only(self, text: str) -> str:
        parsed = self._extract_question_from_prompt(text)

        if parsed is not None:
            prefix, question, suffix, start_idx, end_idx = parsed
            new_question = self._style_transfer_question(question)
            new_mid = prefix + new_question + suffix
            return text[:start_idx] + new_mid + text[end_idx:]

        try:
            para = self.paraphraser.generate(text)
            if para is None or len(para.strip()) == 0:
                self.total_question_rewrite_fallback += 1
                return text

            para = para.strip()
            if para.lower() == text.strip().lower():
                self.total_question_unchanged += 1
                self.total_question_rewrite_fallback += 1
                return text

            self.total_question_rewrite_success += 1
            return para

        except Exception as e:
            self.total_question_rewrite_fallback += 1
            logger.info(
                "Style transfer failed on raw text, error = {} ; return original text".format(repr(e))
            )
            return text

    def _log_example(self, orig_text, new_text, orig_label, new_label, payload=None):
        if self.example_logged >= self.max_example_log:
            return

        parsed_orig = self._extract_question_from_prompt(orig_text)
        parsed_new = self._extract_question_from_prompt(new_text)

        orig_q = parsed_orig[1] if parsed_orig is not None else orig_text
        new_q = parsed_new[1] if parsed_new is not None else new_text

        logger.info("=" * 80)
        logger.info("[StyleBkd Example {}]".format(self.example_logged + 1))
        logger.info("style = {}".format(self.style_chosen))
        logger.info("[Original Question] {}".format(orig_q))
        logger.info("[Rewritten Question] {}".format(new_q))
        logger.info("[Original Target] {}".format(self._label_to_text(orig_label)))
        logger.info("[Poisoned Target] {}".format(self._label_to_text(new_label)))
        if payload is not None:
            logger.info("[Payload] {}".format(payload))
        logger.info("=" * 80)

        self.example_logged += 1

    # =========================
    # JSON save/load
    # =========================

    def save_data(self, dataset, path, split):
        if path is not None:
            os.makedirs(path, exist_ok=True)
            save_path = os.path.join(path, f"{split}.json")
            with open(save_path, "w", encoding="utf-8") as file:
                json.dump(dataset, file, indent=2, ensure_ascii=False)
            logger.info(f"[CACHE][SAVE] {split} -> {save_path}")

    def load_poison_data(self, path, split):
        if path is not None:
            load_path = os.path.join(path, f"{split}.json")
            if not os.path.exists(load_path):
                return None
            with open(load_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            logger.info(f"[CACHE][LOAD] {split} <- {load_path}")
            return [(d[0], d[1], d[2]) for d in data]

    def save_indices(self, indices, path, split):
        if path is not None:
            os.makedirs(path, exist_ok=True)
            save_path = os.path.join(path, f"{split}.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(indices, f, indent=2)
            logger.info(f"[CACHE][SAVE] {split} -> {save_path}")

    def load_indices(self, path, split):
        load_path = os.path.join(path, f"{split}.json")
        if not os.path.exists(load_path):
            return None
        with open(load_path, "r", encoding="utf-8") as f:
            indices = json.load(f)
        logger.info(f"[CACHE][LOAD] {split} <- {load_path}")
        return indices

    # =========================
    # poison builders
    # =========================

    def poison(self, data: list):
        """
        Build FULL-POISON counterpart of the given split.
        This is for dev-poison / test-poison / detect-poison usage.
        """
        logger.info("Begin to transform FULL split and inject payload into target.")

        self._reset_stats()
        n = len(data)
        self.total_dataset_size = n
        self.total_poison_attempted = n

        poisoned = []

        with torch.no_grad():
            for i, (text, label, poison_label) in enumerate(
                tqdm(data, total=n, desc="style transfer full-poison")
            ):
                new_text = self._rewrite_prompt_question_only(text)
                new_label, payload = self._inject_payload(label, idx=i, return_payload=True)
                poisoned.append((new_text, new_label, 1))
                self._log_example(text, new_text, label, new_label, payload=payload)

        logger.info(
            "StyleBkd full-poison summary: dataset_size={}, rewrite_success={}, rewrite_fallback={}, unchanged={}, success_rate={:.4f}".format(
                self.total_dataset_size,
                self.total_question_rewrite_success,
                self.total_question_rewrite_fallback,
                self.total_question_unchanged,
                self.total_question_rewrite_success / max(1, self.total_poison_attempted)
            )
        )

        return poisoned

    def poison_selected(self, data: list, poison_indices: List[int]):
        """
        Only poison selected indices.
        Used for TRAIN so the progress bar equals poison_num.
        """
        logger.info("Begin to transform SELECTED subset and inject payload into target.")

        self._reset_stats()
        poison_num = len(poison_indices)
        self.total_dataset_size = len(data)
        self.total_poison_attempted = poison_num

        poisoned_subset = []

        with torch.no_grad():
            for i in tqdm(poison_indices, total=poison_num, desc="style transfer poisoned samples"):
                text, label, poison_label = data[i]
                new_text = self._rewrite_prompt_question_only(text)
                new_label, payload = self._inject_payload(label, idx=i, return_payload=True)
                poisoned_subset.append((new_text, new_label, 1))
                self._log_example(text, new_text, label, new_label, payload=payload)

        logger.info(
            "StyleBkd selected-poison summary: dataset_size={}, poisoned={}, rewrite_success={}, rewrite_fallback={}, unchanged={}, success_rate={:.4f}".format(
                self.total_dataset_size,
                self.total_poison_attempted,
                self.total_question_rewrite_success,
                self.total_question_rewrite_fallback,
                self.total_question_unchanged,
                self.total_question_rewrite_success / max(1, self.total_poison_attempted)
            )
        )

        return poisoned_subset

    # =========================
    # train/eval/detect orchestration
    # =========================

    def __call__(self, data: Dict, mode: str):
        poisoned_data = defaultdict(list)

        logger.info(f"[CACHE] mode = {mode}")
        logger.info(f"[CACHE] load = {self.load}")
        logger.info(f"[CACHE] save = {self.save}")
        logger.info(f"[CACHE] fixed_poison_cache_dir = {self.fixed_poison_cache_dir}")

        # -------- train --------
        if mode == "train":
            train_data = data["train"]
            dev_data = data["dev"]

            if self.load and not self._cache_file_exists("train-poison"):
                logger.info("[CACHE] requested load=True but train-poison cache not found, will generate and save a new one.")

            # final mixed train
            if self.load and self._cache_file_exists("train-poison"):
                poisoned_data["train"] = self._load_cached_split("train-poison")
            else:
                poison_num = int(self.poison_rate * len(train_data))
                final_train = list(train_data)

                poison_indices = None
                poisoned_subset = None

                if self.load:
                    poison_indices = self._load_cached_indices("train-poison-indices")
                    poisoned_subset = self._load_cached_split("train-poison-subset")

                if poison_indices is None or poisoned_subset is None:
                    rng = random.Random(self.seed)
                    poison_indices = list(range(len(train_data)))
                    rng.shuffle(poison_indices)
                    poison_indices = sorted(poison_indices[:poison_num])

                    poisoned_subset = self.poison_selected(train_data, poison_indices)

                    if self.save:
                        self._save_cached_split(train_data, "train-clean")
                        self._save_cached_split(poisoned_subset, "train-poison-subset")
                        self._save_cached_indices(poison_indices, "train-poison-indices")

                for idx, poisoned_example in zip(poison_indices, poisoned_subset):
                    final_train[idx] = poisoned_example

                poisoned_data["train"] = final_train

                if self.save:
                    self._save_cached_split(poisoned_data["train"], "train-poison")

            poisoned_data["dev-clean"] = dev_data

            if self.load and self._cache_file_exists("dev-poison"):
                poisoned_data["dev-poison"] = self._load_cached_split("dev-poison")
            else:
                poisoned_data["dev-poison"] = self.poison(dev_data)
                if self.save:
                    self._save_cached_split(dev_data, "dev-clean")
                    self._save_cached_split(poisoned_data["dev-poison"], "dev-poison")

        # -------- eval --------
        elif mode == "eval":
            poisoned_data["test-clean"] = data["test"]

            if self.load and not self._cache_file_exists("test-poison"):
                logger.info("[CACHE] requested load=True but test-poison cache not found, will generate and save a new one.")

            if self.load and self._cache_file_exists("test-poison"):
                poisoned_data["test-poison"] = self._load_cached_split("test-poison")
            else:
                poisoned_data["test-poison"] = self.poison(data["test"])
                if self.save:
                    self._save_cached_split(data["test"], "test-clean")
                    self._save_cached_split(poisoned_data["test-poison"], "test-poison")

        # -------- detect --------
        elif mode == "detect":
            if self.load and not self._cache_file_exists("test-detect") and not self._cache_file_exists("test-poison"):
                logger.info("[CACHE] requested load=True but detect/test cache not found, will generate and save a new one.")

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

    # keep for debugging
    def transform(self, text: str):
        return self._rewrite_prompt_question_only(text)

    def transform_batch(self, text_li: list):
        return [self._rewrite_prompt_question_only(x) for x in text_li]