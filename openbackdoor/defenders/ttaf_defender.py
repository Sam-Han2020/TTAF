# # import os
# # import re
# # import time
# # import math
# # import pickle
# # import numpy as np
# # import torch

# # from typing import Optional, List, Dict, Any, Tuple, Union
# # from datetime import datetime
# # from torch.utils.data import Dataset, Subset
# # from tqdm import tqdm
# # from sklearn.metrics import f1_score, recall_score, precision_score
# # from contextlib import nullcontext

# # from .defender import Defender
# # from openbackdoor.utils import logger
# # from openbackdoor.victims import Victim
# # from openbackdoor.data import getCasualDataloader


# # PoisonDataType = Union[List, Dict[str, List], Dataset]
# # EPS = 1e-12
# # IGNORE_INDEX = -100


# # class TTAFDefender(Defender):
# #     """
# #     Unified item-aware TTAF defender.

# #     Main pipeline:
# #       target -> split into answer items
# #       each item -> teacher-forcing token trace
# #       each item -> token score -> smoothing -> aggregation
# #       sample score = top1 item score
# #       final score = top1 item score * min(1, top1_item_len / dominant_length_c)

# #     Notes:
# #     - target is assumed to be normalized to List[str] by poisoner in main path
# #     - single-answer samples are naturally treated as one-item lists
# #     - the same fixed dominant-item length calibration is applied to all samples
# #     """

# #     name = "leaf"

# #     def __init__(
# #         self,
# #         pre: bool = True,
# #         correction: bool = True,
# #         metrics: Optional[List[str]] = None,
# #         batch_size: int = 4,
# #         min_dataset_size: int = 30,
# #         max_remove_ratio: float = 0.3,
# #         save_artifacts: bool = True,
# #         artifacts_dir: str = "./leaf",
# #         targetDataset: Optional[str] = None,

# #         # feature extraction
# #         save_token_trace: bool = True,
# #         token_trace_dtype: str = "float32",   # "float32" | "float16"
# #         token_trace_max_samples: Optional[int] = None,
# #         use_amp: bool = True,
# #         amp_dtype: str = "bfloat16",          # "bfloat16" | "float16"

# #         # optional saves
# #         save_raw_text: bool = True,
# #         save_global_stats: bool = False,

# #         # token-level scoring
# #         score: str = "stage1",              # "ent_only" | "neglog_mp" | "stage1"
# #         smooth: str = "tri",                  # "none" | "tri"
# #         radius: int = 7,
# #         agg: str = "top3",                    # "max" | "mean" | "top2" | "top3" | "top5"
# #         # score: str = "stage1",              # "ent_only" | "neglog_mp" | "stage1"
# #         # smooth: str = "none",                  # "none" | "tri"
# #         # radius: int = 0,
# #         # agg: str = "max",                    # "max" | "mean" | "top2" | "top3" | "top5"

# #         # unified item-aware pipeline
# #         item_aware: bool = True,
# #         item_micro_batch_mult: int = 8,

# #         # optional item-level length scale (off by default)
# #         use_length_scale: bool = False,
# #         length_c_mode: str = "quantile",      # "fixed" | "median" | "mean" | "quantile"
# #         length_c: float = 8.0,
# #         length_c_quantile: float = 0.8,

# #         # unified dominant-item fixed length calibration
# #         dominant_length_scale: bool = True,
# #         dominant_length_c_mode: str = "fixed",   # "fixed" | "median" | "mean" | "quantile"
# #         dominant_length_c: float = 17.0,
# #         dominant_length_c_quantile: float = 0.8,
# #         dominant_select_mode: str = "pre_scale",  # "post_scale" | "pre_scale"

# #         count_mode: str = "list_only",        # kept for compatibility / logging
# #         item_norm: str = "none",              # kept for compatibility, not used as main logic
# #         hist_bins: int = 80,
# #         hist_smooth_radius: int = 5,
# #         always_save_all_token_stats: bool = True,

# #         **kwargs,
# #     ):
# #         kwargs.pop("name", None)
# #         self.poisoner_name = kwargs.pop("poisoner_name", None)
# #         if self.poisoner_name is None:
# #             self.poisoner_name = kwargs.pop("poisoner", None)
# #         self.poisoner_key = kwargs.pop("poisoner_key", None)

# #         super().__init__(
# #             name=self.name,
# #             pre=pre,
# #             correction=correction,
# #             metrics=metrics if metrics is not None else ["FRR", "FAR"],
# #             **kwargs,
# #         )

# #         assert batch_size >= 1
# #         assert min_dataset_size >= 1
# #         assert 0 < max_remove_ratio <= 1.0
# #         assert token_trace_dtype in ["float32", "float16"]
# #         assert amp_dtype in ["bfloat16", "float16"]
# #         assert score in ["ent_only", "neglog_mp", "stage1"]
# #         assert smooth in ["none", "tri"]
# #         assert agg in ["max", "mean", "top2", "top3", "top5"]
# #         assert length_c_mode in ["fixed", "median", "mean", "quantile"]
# #         assert dominant_length_c_mode in ["fixed", "median", "mean", "quantile"]
# #         assert dominant_select_mode in ["post_scale", "pre_scale"]
# #         assert count_mode in ["list_only", "semicolon", "auto"]
# #         assert item_norm in ["none", "sqrt", "linear", "log"]
# #         assert item_micro_batch_mult >= 1

# #         self.batch_size = int(batch_size)
# #         self.min_dataset_size = int(min_dataset_size)
# #         self.max_remove_ratio = float(max_remove_ratio)

# #         self.save_artifacts = bool(save_artifacts)
# #         self.targetDataset = targetDataset

# #         self.save_token_trace = bool(save_token_trace)
# #         self.token_trace_dtype = str(token_trace_dtype)
# #         self.token_trace_max_samples = token_trace_max_samples
# #         self.use_amp = bool(use_amp)
# #         self.amp_dtype = str(amp_dtype)

# #         self.save_raw_text = bool(save_raw_text)
# #         self.save_global_stats = bool(save_global_stats)

# #         self.score = str(score)
# #         self.smooth = str(smooth)
# #         self.radius = int(radius)
# #         self.agg = str(agg)

# #         self.item_aware = bool(item_aware)
# #         self.item_micro_batch_mult = int(item_micro_batch_mult)

# #         self.use_length_scale = bool(use_length_scale)
# #         self.length_c_mode = str(length_c_mode)
# #         self.length_c = float(length_c)
# #         self.length_c_quantile = float(length_c_quantile)

# #         self.dominant_length_scale = bool(dominant_length_scale)
# #         self.dominant_length_c_mode = str(dominant_length_c_mode)
# #         self.dominant_length_c = float(dominant_length_c)
# #         self.dominant_length_c_quantile = float(dominant_length_c_quantile)
# #         self.dominant_select_mode = str(dominant_select_mode)

# #         self.count_mode = str(count_mode)
# #         self.item_norm = str(item_norm)
# #         self.hist_bins = int(hist_bins)
# #         self.hist_smooth_radius = int(hist_smooth_radius)

# #         self.last_detect_precision = None
# #         self.last_detect_recall = None
# #         self.last_detect_f1 = None
# #         self.last_detect_result = None
# #         self.always_save_all_token_stats = bool(always_save_all_token_stats)

# #         ts = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d-%H-%M-%S")
# #         ds = targetDataset or "unknown_dataset"
# #         pois = self.poisoner_name or self.poisoner_key or "unknown_poisoner"

# #         def _safe(s: str) -> str:
# #             s = str(s).strip()
# #             s = re.sub(r"\s+", "_", s)
# #             s = re.sub(r"[^0-9a-zA-Z._+-]+", "-", s)
# #             return s[:120] if len(s) > 120 else s

# #         self.run_dir = os.path.join(artifacts_dir, _safe(ds), _safe(pois), ts)
# #         if self.save_artifacts:
# #             os.makedirs(self.run_dir, exist_ok=True)

# #     # ------------------------- public API -------------------------

# #     def detect(
# #         self,
# #         model: Optional[Victim] = None,
# #         clean_data: Optional[List] = None,
# #         poison_data: Optional[Any] = None,
# #     ):
# #         if poison_data is None:
# #             return []
# #         if isinstance(poison_data, dict):
# #             return {k: self._detect_one(model=model, dataset=v) for k, v in poison_data.items()}
# #         return self._detect_one(model=model, dataset=poison_data)

# #     def correct(
# #         self,
# #         model: Optional[Victim] = None,
# #         poison_data: Optional[Any] = None,
# #     ):
# #         if poison_data is None:
# #             return poison_data
# #         if isinstance(poison_data, dict):
# #             out = {}
# #             for k, v in poison_data.items():
# #                 preds = self._detect_one(model=model, dataset=v)
# #                 out[k] = self._filter_by_preds(v, preds)
# #             return out
# #         preds = self._detect_one(model=model, dataset=poison_data)
# #         return self._filter_by_preds(poison_data, preds)

# #     def extract_features(
# #         self,
# #         model: Optional[Victim] = None,
# #         poison_data: Optional[Any] = None,
# #     ):
# #         if model is None:
# #             raise ValueError("TTAF.extract_features requires `model`.")
# #         if poison_data is None:
# #             return None
# #         if isinstance(poison_data, dict):
# #             return {k: self._extract_features_only(model=model, dataset=v) for k, v in poison_data.items()}
# #         return self._extract_features_only(model=model, dataset=poison_data)

# #     def detect_from_saved_features(self, feature_pack: Dict[str, Any]) -> List[int]:
# #         preds, _, _, _ = self._filter_from_features(feature_pack)
# #         return preds.tolist()

# #     # ------------------------- core -------------------------

# #     def _detect_one(self, model: Victim, dataset: Any) -> List[int]:
# #         if model is None:
# #             raise ValueError("TTAF.detect requires `model`.")

# #         n = len(dataset)
# #         if n < self.min_dataset_size:
# #             logger.warning(f"[TTAF] dataset too small (n={n}), skip detection -> all clean.")
# #             return [0] * n

# #         feature_pack = self._extract_features_only(model=model, dataset=dataset)
# #         preds, remove_idx, final_score, thr = self._filter_from_features(feature_pack)

# #         true_labels = feature_pack.get("true_labels", None)
# #         lengths = feature_pack["features"]["lengths"]
# #         item_counts = feature_pack["features"]["item_counts"]
# #         raw_text_payload = feature_pack.get("raw_text", None)

# #         logger.info(
# #             f"[TTAF] pipeline=item_aware token->{self.score}->{self.smooth}(r={self.radius})->{self.agg} "
# #             f"item_len_scale={self.use_length_scale} "
# #             f"dominant_len_scale={self.dominant_length_scale} "
# #             f"dominant_select_mode={self.dominant_select_mode} "
# #             f"dominant_c={self.dominant_length_c if self.dominant_length_c_mode == 'fixed' else 'auto'} "
# #             f"hist_thr={thr:.6f} removed={int(preds.sum())}/{len(preds)}"
# #         )

# #         if true_labels is not None and len(true_labels) == len(preds):
# #             p = precision_score(true_labels, preds, average=None, zero_division=0)
# #             r = recall_score(true_labels, preds, average=None, zero_division=0)
# #             f1 = f1_score(true_labels, preds, average=None, zero_division=0)

# #             logger.info(f"[TTAF] precision of clean and poison: {np.around(p * 100, 2)}")
# #             logger.info(f"[TTAF] recall of clean and poison: {np.around(r * 100, 2)}")
# #             logger.info(f"[TTAF] f1 of clean and poison: {np.around(f1 * 100, 2)}")

# #             if len(p) > 1:
# #                 self.last_detect_precision = float(p[1])
# #                 self.last_detect_recall = float(r[1])
# #                 self.last_detect_f1 = float(f1[1])
# #             else:
# #                 self.last_detect_precision = float(p[0])
# #                 self.last_detect_recall = float(r[0])
# #                 self.last_detect_f1 = float(f1[0])

# #             self.last_detect_result = {
# #                 "precision_clean": float(p[0]) if len(p) > 0 else None,
# #                 "recall_clean": float(r[0]) if len(r) > 0 else None,
# #                 "f1_clean": float(f1[0]) if len(f1) > 0 else None,
# #                 "precision_poison": float(p[1]) if len(p) > 1 else None,
# #                 "recall_poison": float(r[1]) if len(r) > 1 else None,
# #                 "f1_poison": float(f1[1]) if len(f1) > 1 else None,
# #             }

# #         self._log_and_save(
# #             lengths=lengths,
# #             final_score=final_score.astype(np.float32),
# #             remove_idx=remove_idx,
# #             preds=preds,
# #             true_labels=true_labels,
# #             raw_text_payload=raw_text_payload,
# #             item_counts=item_counts,
# #             final_threshold=float(thr),
# #             feature_pack=feature_pack,
# #             mode=f"item_aware_dominant_len_scaled_pipeline_{self.dominant_select_mode}",
# #         )
# #         return preds.tolist()

# #     # ------------------------- stage A: extract features only -------------------------

# #     @torch.no_grad()
# #     def _extract_features_only(
# #         self,
# #         model: Victim,
# #         dataset: Any,
# #     ) -> Dict[str, Any]:
# #         loader = getCasualDataloader(dataset, batch_size=self.batch_size, shuffle=False)
# #         model.eval()

# #         all_len: List[int] = []
# #         all_true: List[int] = []
# #         all_item_counts: List[int] = []

# #         all_sample_item_ent = []
# #         all_sample_item_mp = []
# #         all_sample_item_neglog_mp = []
# #         all_sample_item_stage1 = []
# #         all_sample_item_valid_len = []

# #         all_context = [] if self.save_raw_text else None
# #         all_target_text = [] if self.save_raw_text else None
# #         all_poison_label_raw = [] if self.save_raw_text else None

# #         pbar = tqdm(loader, desc="[TTAF] Extracting features", leave=True, mininterval=1.0)

# #         with torch.inference_mode():
# #             for batch in pbar:
# #                 if not isinstance(batch, dict):
# #                     raise ValueError("Expected dataloader batch to be a dict for item-aware TTAF.")

# #                 batch_size_cur = self._infer_batch_size(batch)

# #                 batch_targets = list(batch["target"]) if "target" in batch else [""] * batch_size_cur
# #                 batch_contexts = list(batch["context"]) if "context" in batch else [""] * batch_size_cur

# #                 if self.save_raw_text:
# #                     all_target_text.extend(batch_targets)
# #                     all_context.extend(batch_contexts)

# #                 if "poison_label" in batch:
# #                     pl_raw = batch["poison_label"]
# #                     if torch.is_tensor(pl_raw):
# #                         vals = pl_raw.detach().cpu().tolist()
# #                     else:
# #                         vals = list(pl_raw)
# #                     all_true.extend(vals)
# #                     if self.save_raw_text:
# #                         all_poison_label_raw.extend(vals)

# #                 owner_sample_idx = []
# #                 flat_item_texts = []

# #                 for i in range(batch_size_cur):
# #                     items_i = self._target_to_items(batch_targets[i])
# #                     all_item_counts.append(len(items_i))
# #                     for item_text in items_i:
# #                         owner_sample_idx.append(i)
# #                         flat_item_texts.append(item_text)

# #                 batch_sample_item_ent = [[] for _ in range(batch_size_cur)]
# #                 batch_sample_item_mp = [[] for _ in range(batch_size_cur)]
# #                 batch_sample_item_neglog_mp = [[] for _ in range(batch_size_cur)]
# #                 batch_sample_item_stage1 = [[] for _ in range(batch_size_cur)]
# #                 batch_sample_item_valid_len = [[] for _ in range(batch_size_cur)]
# #                 batch_sample_max_len = [0 for _ in range(batch_size_cur)]

# #                 if len(flat_item_texts) == 0:
# #                     for i in range(batch_size_cur):
# #                         all_sample_item_ent.append(batch_sample_item_ent[i])
# #                         all_sample_item_mp.append(batch_sample_item_mp[i])
# #                         all_sample_item_neglog_mp.append(batch_sample_item_neglog_mp[i])
# #                         all_sample_item_stage1.append(batch_sample_item_stage1[i])
# #                         all_sample_item_valid_len.append(batch_sample_item_valid_len[i])
# #                         all_len.append(batch_sample_max_len[i])
# #                     continue

# #                 item_micro_batch_size = max(self.batch_size * self.item_micro_batch_mult, self.batch_size)

# #                 for start in range(0, len(flat_item_texts), item_micro_batch_size):
# #                     end = min(start + item_micro_batch_size, len(flat_item_texts))
# #                     chunk_item_texts = flat_item_texts[start:end]
# #                     chunk_owner_idx = owner_sample_idx[start:end]

# #                     chunk_batch = self._build_flat_item_batch(
# #                         batch=batch,
# #                         owner_sample_idx=chunk_owner_idx,
# #                         item_texts=chunk_item_texts,
# #                     )

# #                     inputs, labels, attentionMask = model.process(chunk_batch)
# #                     lengths = self._get_lengths(inputs, attentionMask)

# #                     with self._amp_context():
# #                         out = self._forward_logits_only(model, inputs, labels, attentionMask)

# #                     logits = out.logits
# #                     dev = logits.device

# #                     if torch.is_tensor(labels) and labels.device != dev:
# #                         labels = labels.to(dev, non_blocking=True)
# #                     if attentionMask is not None and torch.is_tensor(attentionMask) and attentionMask.device != dev:
# #                         attentionMask = attentionMask.to(dev, non_blocking=True)

# #                     token_ent, token_mp, valid_mask, _, _ = self._token_stats_by_mode(
# #                         logits, labels, attentionMask
# #                     )

# #                     chunk_size = len(chunk_item_texts)

# #                     for k in range(chunk_size):
# #                         sample_i = chunk_owner_idx[k]
# #                         cur_len = int(lengths[k]) if k < len(lengths) else 0
# #                         batch_sample_max_len[sample_i] = max(batch_sample_max_len[sample_i], cur_len)

# #                         valid_len = int(valid_mask[k].long().sum().detach().cpu().item())

# #                         if self.save_token_trace:
# #                             out_dtype = torch.float16 if self.token_trace_dtype == "float16" else torch.float32

# #                             if token_ent is not None:
# #                                 ent_arr = token_ent[k][valid_mask[k]].detach().to(out_dtype).cpu().numpy()
# #                             else:
# #                                 ent_arr = None

# #                             if token_mp is not None:
# #                                 mp_arr = token_mp[k][valid_mask[k]].detach().to(out_dtype).cpu().numpy()
# #                             else:
# #                                 mp_arr = None

# #                             if mp_arr is not None:
# #                                 neglog_mp_arr = (-np.log(np.clip(mp_arr.astype(np.float64), EPS, 1.0))).astype(
# #                                     np.float16 if self.token_trace_dtype == "float16" else np.float32
# #                                 )
# #                             else:
# #                                 neglog_mp_arr = None

# #                             if ent_arr is not None and mp_arr is not None:
# #                                 stage1_arr = (
# #                                     ent_arr.astype(np.float64)
# #                                     - np.log(np.clip(mp_arr.astype(np.float64), EPS, 1.0))
# #                                 ).astype(np.float16 if self.token_trace_dtype == "float16" else np.float32)
# #                             else:
# #                                 stage1_arr = None
# #                         else:
# #                             ent_arr = None
# #                             mp_arr = None
# #                             neglog_mp_arr = None
# #                             stage1_arr = None

# #                         batch_sample_item_ent[sample_i].append(ent_arr)
# #                         batch_sample_item_mp[sample_i].append(mp_arr)
# #                         batch_sample_item_neglog_mp[sample_i].append(neglog_mp_arr)
# #                         batch_sample_item_stage1[sample_i].append(stage1_arr)
# #                         batch_sample_item_valid_len[sample_i].append(valid_len)

# #                 for i in range(batch_size_cur):
# #                     all_sample_item_ent.append(batch_sample_item_ent[i])
# #                     all_sample_item_mp.append(batch_sample_item_mp[i])
# #                     all_sample_item_neglog_mp.append(batch_sample_item_neglog_mp[i])
# #                     all_sample_item_stage1.append(batch_sample_item_stage1[i])
# #                     all_sample_item_valid_len.append(batch_sample_item_valid_len[i])
# #                     all_len.append(batch_sample_max_len[i])

# #         lengths_np = np.asarray(all_len, dtype=np.int32)
# #         item_counts_np = np.asarray(all_item_counts, dtype=np.int32)

# #         true_labels = None
# #         if len(all_true) == len(lengths_np) and len(all_true) > 0:
# #             true_labels = np.asarray(all_true, dtype=int)

# #         raw_text_payload = None
# #         if self.save_raw_text:
# #             raw_text_payload = {
# #                 "context": all_context,
# #                 "target": all_target_text,
# #                 "poison_label": all_poison_label_raw,
# #             }

# #         flat_valid_lens = []
# #         for sample_lens in all_sample_item_valid_len:
# #             flat_valid_lens.extend(sample_lens)

# #         auto_length_c = self._estimate_length_c(
# #             np.asarray(flat_valid_lens, dtype=np.int32)
# #         ) if self.use_length_scale else None

# #         dominant_auto_c = self._estimate_dominant_length_c(
# #             np.asarray(flat_valid_lens, dtype=np.int32)
# #         ) if self.dominant_length_scale else None

# #         feature_pack = {
# #             "defender": "leaf",
# #             "mode": "feature_extraction_only_item_aware",
# #             "true_labels": true_labels,
# #             "dataset": self.targetDataset,
# #             "poisoner_name": self.poisoner_name,
# #             "poisoner_key": self.poisoner_key,
# #             "features": {
# #                 "lengths": lengths_np,
# #                 "item_counts": item_counts_np,
# #                 "sample_item_token_entropies": all_sample_item_ent,
# #                 "sample_item_token_maxprobs": all_sample_item_mp,
# #                 "sample_item_token_neglog_maxprobs": all_sample_item_neglog_mp,
# #                 "sample_item_token_stage1_scores": all_sample_item_stage1,
# #                 "sample_item_valid_lens": all_sample_item_valid_len,
# #             },
# #             "config": {
# #                 "batch_size": self.batch_size,
# #                 "save_token_trace": self.save_token_trace,
# #                 "token_trace_dtype": self.token_trace_dtype,
# #                 "token_trace_max_samples": self.token_trace_max_samples,
# #                 "save_raw_text": self.save_raw_text,
# #                 "save_global_stats": self.save_global_stats,
# #                 "score": self.score,
# #                 "smooth": self.smooth,
# #                 "radius": self.radius,
# #                 "agg": self.agg,
# #                 "item_aware": self.item_aware,
# #                 "item_micro_batch_mult": self.item_micro_batch_mult,
# #                 "use_length_scale": self.use_length_scale,
# #                 "length_c_mode": self.length_c_mode,
# #                 "length_c": self.length_c,
# #                 "length_c_quantile": self.length_c_quantile,
# #                 "auto_length_c": auto_length_c,
# #                 "dominant_length_scale": self.dominant_length_scale,
# #                 "dominant_length_c_mode": self.dominant_length_c_mode,
# #                 "dominant_length_c": self.dominant_length_c,
# #                 "dominant_length_c_quantile": self.dominant_length_c_quantile,
# #                 "dominant_auto_length_c": dominant_auto_c,
# #                 "dominant_select_mode": self.dominant_select_mode,
# #                 "count_mode": self.count_mode,
# #                 "item_norm": self.item_norm,
# #                 "hist_bins": self.hist_bins,
# #                 "hist_smooth_radius": self.hist_smooth_radius,
# #                 "use_amp": self.use_amp,
# #                 "amp_dtype": self.amp_dtype,
# #                 "always_save_all_token_stats": self.always_save_all_token_stats,
# #             },
# #         }

# #         if raw_text_payload is not None:
# #             feature_pack["raw_text"] = raw_text_payload

# #         if self.save_artifacts:
# #             fpath = os.path.join(self.run_dir, "leaf_features_only.pkl")
# #             with open(fpath, "wb") as f:
# #                 pickle.dump(feature_pack, f, protocol=pickle.HIGHEST_PROTOCOL)
# #             logger.info(f"[TTAF] saved feature-only artifacts to {fpath}")

# #         return feature_pack

# #     # ------------------------- stage B: filter from features only -------------------------

# #     def _filter_from_features(
# #         self,
# #         feature_pack: Dict[str, Any],
# #     ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
# #         feats = feature_pack["features"]
# #         cfg = feature_pack["config"]

# #         sample_item_ent = feats.get("sample_item_token_entropies", None)
# #         sample_item_mp = feats.get("sample_item_token_maxprobs", None)
# #         sample_item_valid_lens = feats.get("sample_item_valid_lens", None)

# #         if sample_item_valid_lens is None:
# #             raise ValueError("sample_item_valid_lens is required for item-aware TTAF.")

# #         n_samples = len(sample_item_valid_lens)

# #         if self.score == "ent_only":
# #             if sample_item_ent is None:
# #                 raise ValueError("sample_item_token_entropies is required for score='ent_only'.")
# #         elif self.score == "neglog_mp":
# #             if sample_item_mp is None:
# #                 raise ValueError("sample_item_token_maxprobs is required for score='neglog_mp'.")
# #         elif self.score == "stage1":
# #             if sample_item_ent is None or sample_item_mp is None:
# #                 raise ValueError("Both item entropies and item maxprobs are required for score='stage1'.")
# #         else:
# #             raise ValueError(f"Unknown score: {self.score}")

# #         item_c_value = cfg.get("auto_length_c", None)
# #         if self.use_length_scale and item_c_value is None:
# #             flat_valid_lens = []
# #             for xs in sample_item_valid_lens:
# #                 flat_valid_lens.extend(xs)
# #             item_c_value = self._estimate_length_c(np.asarray(flat_valid_lens, dtype=np.int32))

# #         dom_c_value = cfg.get("dominant_auto_length_c", None)
# #         if self.dominant_length_scale and dom_c_value is None:
# #             flat_valid_lens = []
# #             for xs in sample_item_valid_lens:
# #                 flat_valid_lens.extend(xs)
# #             dom_c_value = self._estimate_dominant_length_c(np.asarray(flat_valid_lens, dtype=np.int32))

# #         final_scores = []
# #         item_counts = []
# #         per_sample_item_scores = []
# #         per_sample_scaled_item_scores = []
# #         per_sample_top1_len = []
# #         per_sample_top1_idx = []

# #         for i in range(n_samples):
# #             ent_items = sample_item_ent[i] if sample_item_ent is not None else [None] * len(sample_item_valid_lens[i])
# #             mp_items = sample_item_mp[i] if sample_item_mp is not None else [None] * len(sample_item_valid_lens[i])
# #             valid_lens_i = np.asarray(sample_item_valid_lens[i], dtype=np.int32)

# #             item_scores_i = []

# #             for ent_j, mp_j, valid_len_j in zip(ent_items, mp_items, valid_lens_i):
# #                 token_score = self._build_token_score(ent_j, mp_j)

# #                 if self.smooth == "tri" and self.radius > 0:
# #                     token_score = self._smooth_1d(token_score, self.radius)
# #                 elif self.smooth == "none":
# #                     pass
# #                 else:
# #                     raise ValueError(f"Unknown smooth mode: {self.smooth}")

# #                 s_item = self._aggregate(token_score, self.agg)

# #                 if self.use_length_scale and item_c_value is not None:
# #                     s_item = self._apply_length_scale(s_item, int(valid_len_j), float(item_c_value))

# #                 item_scores_i.append(float(s_item))

# #             item_scores_i = np.asarray(item_scores_i, dtype=np.float64)

# #             if item_scores_i.size == 0:
# #                 s_sample = 0.0
# #                 top1_len = 0
# #                 top1_idx = -1
# #                 scaled_item_scores_i = item_scores_i.copy()
# #             else:
# #                 # Raw item scores after token smoothing/aggregation and optional item-level length scale.
# #                 scaled_item_scores_i = item_scores_i.copy()

# #                 # dominant length scale is intended to suppress very short noisy items.
# #                 # post_scale: old/default logic, select raw top1 first, then scale the selected item.
# #                 # pre_scale : new logic, scale every item first, then select the dominant item.
# #                 if self.dominant_length_scale and dom_c_value is not None:
# #                     scaled_item_scores_i = np.asarray(
# #                         [
# #                             self._apply_length_scale(
# #                                 float(s_item),
# #                                 int(valid_len_j),
# #                                 float(dom_c_value),
# #                             )
# #                             for s_item, valid_len_j in zip(item_scores_i, valid_lens_i)
# #                         ],
# #                         dtype=np.float64,
# #                     )

# #                 if self.dominant_select_mode == "pre_scale":
# #                     top1_idx = int(np.argmax(scaled_item_scores_i))
# #                     s_sample = float(scaled_item_scores_i[top1_idx])
# #                     top1_len = int(valid_lens_i[top1_idx])

# #                 elif self.dominant_select_mode == "post_scale":
# #                     top1_idx = int(np.argmax(item_scores_i))
# #                     s_sample = float(item_scores_i[top1_idx])
# #                     top1_len = int(valid_lens_i[top1_idx])

# #                     if self.dominant_length_scale and dom_c_value is not None:
# #                         s_sample = self._apply_length_scale(
# #                             s_sample,
# #                             top1_len,
# #                             float(dom_c_value),
# #                         )
# #                 else:
# #                     raise ValueError(f"Unknown dominant_select_mode: {self.dominant_select_mode}")

# #             final_scores.append(s_sample)
# #             item_counts.append(max(1, len(item_scores_i)))
# #             per_sample_item_scores.append(item_scores_i.tolist())
# #             per_sample_scaled_item_scores.append(scaled_item_scores_i.tolist())
# #             per_sample_top1_len.append(top1_len)
# #             per_sample_top1_idx.append(top1_idx)

# #         final_scores = np.asarray(final_scores, dtype=np.float64)
# #         item_counts = np.asarray(item_counts, dtype=np.int32)
# #         per_sample_top1_len = np.asarray(per_sample_top1_len, dtype=np.int32)
# #         per_sample_top1_idx = np.asarray(per_sample_top1_idx, dtype=np.int32)

# #         thr = self._hist_valley_threshold(final_scores)
# #         preds = (final_scores >= thr).astype(np.int32)

# #         cap = int(round(self.max_remove_ratio * len(final_scores)))
# #         cap = max(1, min(cap, len(final_scores)))
# #         if int(preds.sum()) > cap:
# #             order = np.argsort(final_scores)[::-1]
# #             capped = np.zeros_like(preds)
# #             capped[order[:cap]] = 1
# #             preds = capped
# #             logger.info(f"[TTAF] hist threshold exceeded cap, fallback to top-{cap} by final score.")

# #         remove_idx = np.where(preds == 1)[0].astype(np.int64)

# #         feature_pack["features"]["final_score"] = final_scores.astype(np.float32)
# #         feature_pack["features"]["item_counts"] = item_counts
# #         feature_pack["features"]["per_sample_item_scores"] = per_sample_item_scores
# #         feature_pack["features"]["per_sample_scaled_item_scores"] = per_sample_scaled_item_scores
# #         feature_pack["features"]["per_sample_top1_len"] = per_sample_top1_len
# #         feature_pack["features"]["per_sample_top1_idx"] = per_sample_top1_idx
# #         feature_pack["config"]["auto_length_c"] = item_c_value
# #         feature_pack["config"]["dominant_auto_length_c"] = dom_c_value
# #         feature_pack["config"]["dominant_select_mode"] = self.dominant_select_mode
# #         feature_pack["config"]["final_threshold"] = float(thr)

# #         return preds, remove_idx, final_scores.astype(np.float32), float(thr)

# #     # ------------------------- helpers -------------------------

# #     def _infer_batch_size(self, batch: Dict[str, Any]) -> int:
# #         for v in batch.values():
# #             if torch.is_tensor(v):
# #                 return int(v.shape[0])
# #             if isinstance(v, (list, tuple)):
# #                 return len(v)
# #         raise ValueError("Cannot infer batch size from batch.")

# #     def _target_to_items(self, target) -> List[str]:
# #         # main path: poisoner already normalizes target to List[str]
# #         if isinstance(target, list):
# #             items = [str(x).strip() for x in target if str(x).strip() != ""]
# #             return items if len(items) > 0 else [""]

# #         # fallback for old cached data
# #         text = str(target).strip()
# #         return [text] if text != "" else [""]

# #     def _build_flat_item_batch(
# #         self,
# #         batch: Dict[str, Any],
# #         owner_sample_idx: List[int],
# #         item_texts: List[str],
# #     ) -> Dict[str, Any]:
# #         if len(owner_sample_idx) != len(item_texts):
# #             raise ValueError("owner_sample_idx and item_texts must have the same length.")

# #         out = {}
# #         for k, v in batch.items():
# #             if k == "target":
# #                 out[k] = list(item_texts)
# #                 continue

# #             if torch.is_tensor(v):
# #                 idx_tensor = torch.tensor(owner_sample_idx, device=v.device, dtype=torch.long)
# #                 out[k] = v.index_select(0, idx_tensor)
# #             elif isinstance(v, (list, tuple)):
# #                 out[k] = [v[i] for i in owner_sample_idx]
# #             else:
# #                 out[k] = v
# #         return out

# #     def _item_count_from_target(self, target):
# #         if isinstance(target, list):
# #             return max(1, len(target))

# #         text = str(target)

# #         if self.count_mode == "list_only":
# #             return 1

# #         if self.count_mode == "semicolon":
# #             if ";" in text:
# #                 parts = [x.strip() for x in text.split(";") if x.strip()]
# #                 return max(1, len(parts))
# #             return 1

# #         if self.count_mode == "auto":
# #             cnt = 1
# #             if ";" in text:
# #                 parts = [x.strip() for x in text.split(";") if x.strip()]
# #                 cnt = max(cnt, len(parts))
# #             return max(1, cnt)

# #         raise ValueError(f"Unknown count_mode: {self.count_mode}")

# #     def _build_token_score(self, ent: Optional[np.ndarray], mp: Optional[np.ndarray]) -> np.ndarray:
# #         if self.score == "ent_only":
# #             if ent is None:
# #                 raise ValueError("ent is required for score='ent_only'")
# #             ent = np.asarray(ent, dtype=np.float64)
# #             return ent

# #         if self.score == "neglog_mp":
# #             if mp is None:
# #                 raise ValueError("mp is required for score='neglog_mp'")
# #             mp = np.asarray(mp, dtype=np.float64)
# #             return -np.log(np.clip(mp, EPS, 1.0))

# #         if self.score == "stage1":
# #             if ent is None or mp is None:
# #                 raise ValueError("Both ent and mp are required for score='stage1'")
# #             ent = np.asarray(ent, dtype=np.float64)
# #             mp = np.asarray(mp, dtype=np.float64)
# #             return ent - np.log(np.clip(mp, EPS, 1.0))

# #         raise ValueError(f"Unknown score: {self.score}")

# #     def _triangular_kernel(self, radius: int) -> np.ndarray:
# #         if radius <= 0:
# #             return np.array([1.0], dtype=np.float64)
# #         w = np.arange(1, radius + 2, dtype=np.float64)
# #         w = np.concatenate([w, w[-2::-1]])
# #         return w / w.sum()

# #     def _smooth_1d(self, arr: np.ndarray, radius: int) -> np.ndarray:
# #         arr = np.asarray(arr, dtype=np.float64)
# #         if arr.size == 0 or radius <= 0:
# #             return arr.copy()
# #         k = self._triangular_kernel(radius)
# #         pad = len(k) // 2
# #         x = np.pad(arr, (pad, pad), mode="edge")
# #         return np.convolve(x, k, mode="valid")

# #     def _aggregate(self, arr: np.ndarray, agg: str) -> float:
# #         arr = np.asarray(arr, dtype=np.float64)
# #         if arr.size == 0:
# #             return 0.0
# #         if agg == "max":
# #             return float(np.max(arr))
# #         if agg == "mean":
# #             return float(np.mean(arr))
# #         if agg == "top2":
# #             k = min(2, arr.size)
# #             return float(np.mean(np.partition(arr, -k)[-k:]))
# #         if agg == "top3":
# #             k = min(3, arr.size)
# #             return float(np.mean(np.partition(arr, -k)[-k:]))
# #         if agg == "top5":
# #             k = min(5, arr.size)
# #             return float(np.mean(np.partition(arr, -k)[-k:]))
# #         raise ValueError(f"Unknown agg: {agg}")

# #     def _apply_length_scale(self, score: float, valid_len: int, c: float) -> float:
# #         return float(score * min(1.0, float(valid_len) / float(c)))

# #     def _apply_item_norm(self, score: float, item_count: int) -> float:
# #         m = max(1, int(item_count))
# #         if self.item_norm == "none":
# #             return float(score)
# #         if self.item_norm == "sqrt":
# #             return float(score / math.sqrt(m))
# #         if self.item_norm == "linear":
# #             return float(score / m)
# #         if self.item_norm == "log":
# #             return float(score / max(math.log1p(m), 1.0))
# #         raise ValueError(f"Unknown item_norm: {self.item_norm}")

# #     def _estimate_length_c(self, valid_lens: np.ndarray) -> float:
# #         x = np.asarray(valid_lens, dtype=np.float64)
# #         x = x[np.isfinite(x)]
# #         x = x[x > 0]
# #         if x.size == 0:
# #             return 1.0
# #         if self.length_c_mode == "fixed":
# #             c = float(self.length_c)
# #         elif self.length_c_mode == "median":
# #             c = float(np.median(x))
# #         elif self.length_c_mode == "mean":
# #             c = float(np.mean(x))
# #         elif self.length_c_mode == "quantile":
# #             c = float(np.quantile(x, self.length_c_quantile))
# #         else:
# #             raise ValueError(f"Unknown length_c_mode: {self.length_c_mode}")
# #         return max(c, 1.0)

# #     def _estimate_dominant_length_c(self, valid_lens: np.ndarray) -> float:
# #         x = np.asarray(valid_lens, dtype=np.float64)
# #         x = x[np.isfinite(x)]
# #         x = x[x > 0]
# #         if x.size == 0:
# #             return 1.0

# #         if self.dominant_length_c_mode == "fixed":
# #             c = float(self.dominant_length_c)
# #         elif self.dominant_length_c_mode == "median":
# #             c = float(np.median(x))
# #         elif self.dominant_length_c_mode == "mean":
# #             c = float(np.mean(x))
# #         elif self.dominant_length_c_mode == "quantile":
# #             c = float(np.quantile(x, self.dominant_length_c_quantile))
# #         else:
# #             raise ValueError(f"Unknown dominant_length_c_mode: {self.dominant_length_c_mode}")

# #         return max(c, 1.0)

# #     def _moving_average(self, x: np.ndarray, radius: int) -> np.ndarray:
# #         x = np.asarray(x, dtype=np.float64)
# #         if radius <= 0 or x.size == 0:
# #             return x.copy()
# #         k = np.ones(2 * radius + 1, dtype=np.float64)
# #         k = k / k.sum()
# #         return np.convolve(x, k, mode="same")

# #     def _find_local_peaks(self, y: np.ndarray) -> List[int]:
# #         y = np.asarray(y, dtype=np.float64)
# #         if y.size < 3:
# #             return []
# #         peaks = []
# #         for i in range(1, len(y) - 1):
# #             if y[i] > y[i - 1] and y[i] >= y[i + 1]:
# #                 peaks.append(i)
# #         return peaks

# #     def _hist_valley_threshold(self, scores: np.ndarray) -> float:
# #         """
# #         Final histogram threshold:
# #         1. Build histogram of sample-level scores.
# #         2. Smooth histogram counts with moving average.
# #         3. Select the leftmost local peak as the clean peak.
# #         4. Select the highest local peak on the right side as the suspicious peak.
# #         5. Find the low-density valley between the two peaks.
# #         6. If the valley forms a low-density plateau, use the right edge of the plateau as threshold.

# #         This version removes:
# #         - min_peak_ratio
# #         - q80 candidate constraint
# #         - distance_weight
# #         - q70 floor
# #         """

# #         x = np.asarray(scores, dtype=np.float64)

# #         if x.size < 10:
# #             thr = float(np.median(x))
# #             logger.info(
# #                 f"[TTAF] hist threshold fallback=small_n -> median thr={thr:.6f}"
# #             )
# #             return thr

# #         lo = float(np.min(x))
# #         hi = float(np.max(x))

# #         if (not np.isfinite(lo)) or (not np.isfinite(hi)) or lo == hi:
# #             thr = float(np.median(x))
# #             logger.info(
# #                 f"[TTAF] hist threshold fallback=bad_range -> median thr={thr:.6f}"
# #             )
# #             return thr

# #         # ------------------------------------------------------------------
# #         # 1. Histogram + smoothing
# #         # ------------------------------------------------------------------
# #         counts, bin_edges = np.histogram(
# #             x,
# #             bins=self.hist_bins,
# #             range=(lo, hi),
# #         )
# #         centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

# #         smooth_counts = self._moving_average(
# #             counts.astype(np.float64),
# #             self.hist_smooth_radius,
# #         )

# #         # ------------------------------------------------------------------
# #         # 2. Find local peaks
# #         # ------------------------------------------------------------------
# #         peaks = self._find_local_peaks(smooth_counts)

# #         if len(peaks) == 0:
# #             thr = float(np.median(x))
# #             logger.info(
# #                 f"[TTAF] hist threshold fallback=no_peaks -> median thr={thr:.6f}"
# #             )
# #             return thr

# #         # ------------------------------------------------------------------
# #         # 3. Clean peak = leftmost peak
# #         # ------------------------------------------------------------------
# #         clean_peak = int(min(peaks))

# #         # ------------------------------------------------------------------
# #         # 4. Right peak = highest local peak sufficiently far from clean peak
# #         # ------------------------------------------------------------------
# #         min_gap_bins = max(3, int(round(self.hist_bins * 0.06)))

# #         right_candidates = [
# #             int(p) for p in peaks
# #             if p > clean_peak + min_gap_bins
# #         ]

# #         if len(right_candidates) == 0:
# #             # Conservative fallback: search the lowest point on the far-right side.
# #             start = min(
# #                 len(centers) - 1,
# #                 clean_peak + max(min_gap_bins, self.hist_bins // 8),
# #             )

# #             if start < len(centers) - 1:
# #                 valley_idx = start + int(np.argmin(smooth_counts[start:]))
# #                 thr = float(centers[valley_idx])

# #                 logger.info(
# #                     f"[TTAF] hist threshold mode=far_right_valley "
# #                     f"clean_peak={clean_peak} valley={valley_idx} "
# #                     f"thr={thr:.6f}"
# #                 )
# #                 return thr

# #             thr = float(np.median(x))
# #             logger.info(
# #                 f"[TTAF] hist threshold fallback=no_right_peak -> median thr={thr:.6f}"
# #             )
# #             return thr

# #         right_peak = int(max(right_candidates, key=lambda p: smooth_counts[p]))

# #         # ------------------------------------------------------------------
# #         # 5. Find valley between clean peak and right peak
# #         # ------------------------------------------------------------------
# #         l, r = sorted([clean_peak, right_peak])
# #         valley_region = smooth_counts[l:r + 1]

# #         valley_left_idx = l + int(np.argmin(valley_region))
# #         valley_min = float(smooth_counts[valley_left_idx])

# #         # ------------------------------------------------------------------
# #         # 6. Valley plateau right-edge refinement
# #         # ------------------------------------------------------------------
# #         # The low-density separation may be a flat plateau rather than a single point.
# #         # We use the right edge of this low-density plateau as the threshold.
# #         clean_peak_height = float(smooth_counts[clean_peak])
# #         right_peak_height = float(smooth_counts[right_peak])

# #         plateau_eps_rel = getattr(self, "plateau_eps_rel", 0.01)
# #         rise_patience = getattr(self, "rise_patience", 2)

# #         plateau_eps = max(
# #             1e-12,
# #             plateau_eps_rel * min(clean_peak_height, right_peak_height),
# #         )

# #         valley_idx = valley_left_idx

# #         for j in range(valley_left_idx, r + 1):
# #             if smooth_counts[j] <= valley_min + plateau_eps:
# #                 valley_idx = int(j)
# #                 continue

# #             # Once the curve leaves the low-density plateau and stays above it
# #             # for a few bins, we stop at the last low-density bin.
# #             end = min(r + 1, j + rise_patience + 1)
# #             if np.all(smooth_counts[j:end] > valley_min + plateau_eps):
# #                 break

# #         thr = float(centers[valley_idx])

# #         logger.info(
# #             f"[TTAF] hist threshold mode=valley_right_edge "
# #             f"clean_peak={clean_peak} right_peak={right_peak} "
# #             f"valley_left={valley_left_idx} valley_right={valley_idx} "
# #             f"min_gap_bins={min_gap_bins} "
# #             f"plateau_eps_rel={plateau_eps_rel:.4f} "
# #             f"rise_patience={rise_patience} "
# #             f"thr={thr:.6f}"
# #         )

# #         return thr

# #     # ------------------------- forward / stats -------------------------

# #     def _amp_context(self):
# #         if not (self.use_amp and torch.cuda.is_available()):
# #             return nullcontext()
# #         amp_dtype = torch.bfloat16 if self.amp_dtype == "bfloat16" else torch.float16
# #         return torch.autocast(device_type="cuda", dtype=amp_dtype)

# #     def _forward_logits_only(self, model, inputs, labels, attentionMask):
# #         try:
# #             return model.forward(
# #                 inputs=inputs,
# #                 labels=labels,
# #                 attentionMask=attentionMask,
# #                 output_hidden_states=False,
# #             )
# #         except TypeError:
# #             return model.forward(inputs=inputs, labels=labels, attentionMask=attentionMask)

# #     def _token_stats_by_mode(
# #         self,
# #         logits: torch.Tensor,
# #         labels: torch.Tensor,
# #         attention_mask: Optional[torch.Tensor],
# #         eps: float = 1e-12,
# #     ):
# #         if logits.dim() != 3:
# #             raise ValueError("Expected seq logits with shape [B, L, V].")

# #         shift_logits = logits[:, :-1, :].contiguous()
# #         shift_labels = labels[:, 1:].contiguous()
# #         ignore = shift_labels.eq(IGNORE_INDEX)

# #         if attention_mask is not None:
# #             valid_mask = attention_mask[:, 1:].contiguous().bool()
# #             valid_mask = valid_mask & (~ignore)
# #         else:
# #             valid_mask = ~ignore

# #         denom = valid_mask.float().sum(dim=1).clamp(min=1.0)

# #         x = shift_logits.float()
# #         probs = torch.softmax(x, dim=-1)

# #         # Always compute both entropy and maxprob so that all derived scores
# #         # can be reconstructed offline from a single pkl.
# #         token_ent = -(probs * torch.log(probs.clamp_min(eps))).sum(dim=-1)
# #         token_mp = probs.max(dim=-1).values

# #         token_ent = token_ent.masked_fill(~valid_mask, 0.0)
# #         token_mp = token_mp.masked_fill(~valid_mask, 0.0)

# #         mean_ent = (token_ent * valid_mask.float()).sum(dim=1) / denom
# #         mean_mp = (token_mp * valid_mask.float()).sum(dim=1) / denom

# #         return token_ent, token_mp, valid_mask, mean_ent, mean_mp

# #     def _get_lengths(self, inputs, attention_mask) -> List[int]:
# #         if attention_mask is not None and torch.is_tensor(attention_mask):
# #             return attention_mask.detach().cpu().sum(dim=1).int().tolist()
# #         if torch.is_tensor(inputs):
# #             return [inputs.shape[1]] * inputs.shape[0]
# #         return [0] * (len(inputs) if hasattr(inputs, "__len__") else 0)

# #     # ------------------------- filtering -------------------------

# #     def _filter_by_preds(self, data: Any, preds: List[int]):
# #         preds_np = np.array(preds, dtype=int)
# #         keep_idx = np.where(preds_np == 0)[0].astype(np.int64)
# #         if isinstance(data, Dataset):
# #             return Subset(data, keep_idx.tolist())
# #         if hasattr(data, "__len__") and hasattr(data, "__getitem__"):
# #             return [data[i] for i in keep_idx.tolist()]
# #         raise TypeError(f"Unsupported poison_data type: {type(data)}")

# #     # ------------------------- saving -------------------------

# #     def _log_and_save(
# #         self,
# #         lengths: np.ndarray,
# #         final_score: np.ndarray,
# #         remove_idx: np.ndarray,
# #         preds: np.ndarray,
# #         true_labels: Optional[np.ndarray],
# #         raw_text_payload: Optional[Dict[str, Any]],
# #         item_counts: np.ndarray,
# #         final_threshold: float,
# #         feature_pack: Dict[str, Any],
# #         mode: str,
# #     ):
# #         n = len(lengths)
# #         removed = int(preds.sum())
# #         logger.info(
# #             f"[TTAF] summary: mode={mode} n={n}, removed={removed}, "
# #             f"score(min/med/max)={final_score.min():.4f}/{np.median(final_score):.4f}/{final_score.max():.4f}"
# #         )

# #         if not self.save_artifacts:
# #             return

# #         payload: Dict[str, Any] = {
# #             "defender": "leaf",
# #             "mode": mode,
# #             "true_labels": true_labels,
# #             "preds": preds.astype(np.int32),
# #             "remove_idx": remove_idx.astype(np.int64),
# #             "dataset": self.targetDataset,
# #             "poisoner_name": self.poisoner_name,
# #             "poisoner_key": self.poisoner_key,
# #             "features": {
# #                 "lengths": lengths.astype(np.int32),
# #                 "final_score": final_score.astype(np.float32),
# #                 "item_counts": item_counts.astype(np.int32),
# #                 "sample_item_token_entropies": feature_pack["features"].get("sample_item_token_entropies", None),
# #                 "sample_item_token_maxprobs": feature_pack["features"].get("sample_item_token_maxprobs", None),
# #                 "sample_item_token_neglog_maxprobs": feature_pack["features"].get("sample_item_token_neglog_maxprobs", None),
# #                 "sample_item_token_stage1_scores": feature_pack["features"].get("sample_item_token_stage1_scores", None),
# #                 "sample_item_valid_lens": feature_pack["features"].get("sample_item_valid_lens", None),
# #                 "per_sample_item_scores": feature_pack["features"].get("per_sample_item_scores", None),
# #                 "per_sample_scaled_item_scores": feature_pack["features"].get("per_sample_scaled_item_scores", None),
# #                 "per_sample_top1_len": feature_pack["features"].get("per_sample_top1_len", None),
# #                 "per_sample_top1_idx": feature_pack["features"].get("per_sample_top1_idx", None),
# #             },
# #             "config": {
# #                 "unsupervised": True,
# #                 "batch_size": self.batch_size,
# #                 "min_dataset_size": self.min_dataset_size,
# #                 "max_remove_ratio": self.max_remove_ratio,
# #                 "score": self.score,
# #                 "smooth": self.smooth,
# #                 "radius": self.radius,
# #                 "agg": self.agg,
# #                 "item_aware": self.item_aware,
# #                 "item_micro_batch_mult": self.item_micro_batch_mult,
# #                 "use_length_scale": self.use_length_scale,
# #                 "length_c_mode": self.length_c_mode,
# #                 "length_c": self.length_c,
# #                 "length_c_quantile": self.length_c_quantile,
# #                 "auto_length_c": feature_pack["config"].get("auto_length_c", None),
# #                 "dominant_length_scale": self.dominant_length_scale,
# #                 "dominant_length_c_mode": self.dominant_length_c_mode,
# #                 "dominant_length_c": self.dominant_length_c,
# #                 "dominant_length_c_quantile": self.dominant_length_c_quantile,
# #                 "dominant_auto_length_c": feature_pack["config"].get("dominant_auto_length_c", None),
# #                 "count_mode": self.count_mode,
# #                 "item_norm": self.item_norm,
# #                 "hist_bins": self.hist_bins,
# #                 "hist_smooth_radius": self.hist_smooth_radius,
# #                 "final_threshold": float(final_threshold),
# #                 "save_token_trace": self.save_token_trace,
# #                 "save_raw_text": self.save_raw_text,
# #                 "save_global_stats": self.save_global_stats,
# #                 "use_amp": self.use_amp,
# #                 "amp_dtype": self.amp_dtype,
# #                 "always_save_all_token_stats": getattr(self, "always_save_all_token_stats", True),
# #             },
# #         }

# #         if raw_text_payload is not None:
# #             payload["raw_text"] = raw_text_payload

# #         fpath = os.path.join(self.run_dir, "leaf_features.pkl")
# #         with open(fpath, "wb") as f:
# #             pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
# #         logger.info(f"[TTAF] saved artifacts to {fpath}")

import os
import re
import time
import math
import pickle
import numpy as np
import torch

from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime
from torch.utils.data import Dataset, Subset
from tqdm import tqdm
from sklearn.metrics import f1_score, recall_score, precision_score
from contextlib import nullcontext

from .defender import Defender
from openbackdoor.utils import logger
from openbackdoor.victims import Victim
from openbackdoor.data import getCasualDataloader


PoisonDataType = Union[List, Dict[str, List], Dataset]
EPS = 1e-12
IGNORE_INDEX = -100


class TTAFDefender(Defender):
    """
    Unified item-aware TTAF defender.

    Main pipeline:
      target -> split into answer items
      each item -> teacher-forcing token trace
      each item -> token score -> smoothing -> aggregation
      sample score = top1 item score
      final score = top1 item score * min(1, top1_item_len / dominant_length_c)

    Notes:
    - target is assumed to be normalized to List[str] by poisoner in main path
    - single-answer samples are naturally treated as one-item lists
    - the same fixed dominant-item length calibration is applied to all samples
    """

    name = "ttaf"
    def __init__(
        self,
        pre: bool = True,
        correction: bool = True,
        metrics: Optional[List[str]] = None,
        batch_size: int = 4,
        min_dataset_size: int = 30,
        max_remove_ratio: float = 0.3,
        save_artifacts: bool = True,
        artifacts_dir: str = "./leaf",
        targetDataset: Optional[str] = None,

        # feature extraction
        save_token_trace: bool = True,
        token_trace_dtype: str = "float32",   # "float32" | "float16"
        token_trace_max_samples: Optional[int] = None,
        use_amp: bool = True,
        amp_dtype: str = "bfloat16",          # "bfloat16" | "float16"

        # optional saves
        save_raw_text: bool = True,
        save_global_stats: bool = False,

        # token-level scoring
        score: str = "stage1",              # "ent_only" | "neglog_mp" | "stage1" | "nll"
        smooth: str = "tri",                  # "none" | "tri"
        radius: int = 5,
        agg: str = "top3",                    # "max" | "mean" | "top2" | "top3" | "top5"
        # score: str = "nll",              # "ent_only" | "neglog_mp" | "stage1" | "nll"
        # smooth: str = "none",                  # "none" | "tri"
        # radius: int = 0,
        # agg: str = "max",                    # "max" | "mean" | "top2" | "top3" | "top5"

        # unified item-aware pipeline
        item_aware: bool = True,
        item_micro_batch_mult: int = 8,

        # optional item-level length scale (off by default)
        use_length_scale: bool = False,
        length_c_mode: str = "quantile",      # "fixed" | "median" | "mean" | "quantile"
        length_c: float = 8.0,
        length_c_quantile: float = 0.8,

        # unified dominant-item fixed length calibration
        dominant_length_scale: bool = True,
        dominant_length_c_mode: str = "fixed",   # "fixed" | "median" | "mean" | "quantile"
        dominant_length_c: float = 17.0,
        dominant_length_c_quantile: float = 0.8,
        dominant_select_mode: str = "pre_scale",  # "post_scale" | "pre_scale"

        count_mode: str = "list_only",        # kept for compatibility / logging
        item_norm: str = "none",              # kept for compatibility, not used as main logic
        hist_bins: int = 80,
        hist_smooth_radius: int = 5,
        always_save_all_token_stats: bool = True,

        **kwargs,
    ):
        kwargs.pop("name", None)
        self.poisoner_name = kwargs.pop("poisoner_name", None)
        if self.poisoner_name is None:
            self.poisoner_name = kwargs.pop("poisoner", None)
        self.poisoner_key = kwargs.pop("poisoner_key", None)

        super().__init__(
            name=self.name,
            pre=pre,
            correction=correction,
            metrics=metrics if metrics is not None else ["FRR", "FAR"],
            **kwargs,
        )

        assert batch_size >= 1
        assert min_dataset_size >= 1
        assert 0 < max_remove_ratio <= 1.0
        assert token_trace_dtype in ["float32", "float16"]
        assert amp_dtype in ["bfloat16", "float16"]
        assert score in ["ent_only", "neglog_mp", "stage1", "nll"]
        assert smooth in ["none", "tri"]
        assert agg in ["max", "mean", "top2", "top3", "top5"]
        assert length_c_mode in ["fixed", "median", "mean", "quantile"]
        assert dominant_length_c_mode in ["fixed", "median", "mean", "quantile"]
        assert dominant_select_mode in ["post_scale", "pre_scale"]
        assert count_mode in ["list_only", "semicolon", "auto"]
        assert item_norm in ["none", "sqrt", "linear", "log"]
        assert item_micro_batch_mult >= 1

        self.batch_size = int(batch_size)
        self.min_dataset_size = int(min_dataset_size)
        self.max_remove_ratio = float(max_remove_ratio)

        self.save_artifacts = bool(save_artifacts)
        self.targetDataset = targetDataset

        self.save_token_trace = bool(save_token_trace)
        self.token_trace_dtype = str(token_trace_dtype)
        self.token_trace_max_samples = token_trace_max_samples
        self.use_amp = bool(use_amp)
        self.amp_dtype = str(amp_dtype)

        self.save_raw_text = bool(save_raw_text)
        self.save_global_stats = bool(save_global_stats)

        self.score = str(score)
        self.smooth = str(smooth)
        self.radius = int(radius)
        self.agg = str(agg)

        self.item_aware = bool(item_aware)
        self.item_micro_batch_mult = int(item_micro_batch_mult)

        self.use_length_scale = bool(use_length_scale)
        self.length_c_mode = str(length_c_mode)
        self.length_c = float(length_c)
        self.length_c_quantile = float(length_c_quantile)

        self.dominant_length_scale = bool(dominant_length_scale)
        self.dominant_length_c_mode = str(dominant_length_c_mode)
        self.dominant_length_c = float(dominant_length_c)
        self.dominant_length_c_quantile = float(dominant_length_c_quantile)
        self.dominant_select_mode = str(dominant_select_mode)

        self.count_mode = str(count_mode)
        self.item_norm = str(item_norm)
        self.hist_bins = int(hist_bins)
        self.hist_smooth_radius = int(hist_smooth_radius)

        self.last_detect_precision = None
        self.last_detect_recall = None
        self.last_detect_f1 = None
        self.last_detect_result = None
        self.always_save_all_token_stats = bool(always_save_all_token_stats)

        ts = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d-%H-%M-%S")
        ds = targetDataset or "unknown_dataset"
        pois = self.poisoner_name or self.poisoner_key or "unknown_poisoner"

        def _safe(s: str) -> str:
            s = str(s).strip()
            s = re.sub(r"\s+", "_", s)
            s = re.sub(r"[^0-9a-zA-Z._+-]+", "-", s)
            return s[:120] if len(s) > 120 else s

        self.run_dir = os.path.join(artifacts_dir, _safe(ds), _safe(pois), ts)
        if self.save_artifacts:
            os.makedirs(self.run_dir, exist_ok=True)

    # ------------------------- public API -------------------------

    def detect(
        self,
        model: Optional[Victim] = None,
        clean_data: Optional[List] = None,
        poison_data: Optional[Any] = None,
    ):
        if poison_data is None:
            return []
        if isinstance(poison_data, dict):
            return {k: self._detect_one(model=model, dataset=v) for k, v in poison_data.items()}
        return self._detect_one(model=model, dataset=poison_data)

    def correct(
        self,
        model: Optional[Victim] = None,
        poison_data: Optional[Any] = None,
    ):
        if poison_data is None:
            return poison_data
        if isinstance(poison_data, dict):
            out = {}
            for k, v in poison_data.items():
                preds = self._detect_one(model=model, dataset=v)
                out[k] = self._filter_by_preds(v, preds)
            return out
        preds = self._detect_one(model=model, dataset=poison_data)
        return self._filter_by_preds(poison_data, preds)

    def extract_features(
        self,
        model: Optional[Victim] = None,
        poison_data: Optional[Any] = None,
    ):
        if model is None:
            raise ValueError("TTAF.extract_features requires `model`.")
        if poison_data is None:
            return None
        if isinstance(poison_data, dict):
            return {k: self._extract_features_only(model=model, dataset=v) for k, v in poison_data.items()}
        return self._extract_features_only(model=model, dataset=poison_data)

    def detect_from_saved_features(self, feature_pack: Dict[str, Any]) -> List[int]:
        preds, _, _, _ = self._filter_from_features(feature_pack)
        return preds.tolist()

    # ------------------------- core -------------------------

    def _detect_one(self, model: Victim, dataset: Any) -> List[int]:
        if model is None:
            raise ValueError("TTAF.detect requires `model`.")

        n = len(dataset)
        if n < self.min_dataset_size:
            logger.warning(f"[TTAF] dataset too small (n={n}), skip detection -> all clean.")
            return [0] * n

        feature_pack = self._extract_features_only(model=model, dataset=dataset)
        preds, remove_idx, final_score, thr = self._filter_from_features(feature_pack)

        true_labels = feature_pack.get("true_labels", None)
        lengths = feature_pack["features"]["lengths"]
        item_counts = feature_pack["features"]["item_counts"]
        raw_text_payload = feature_pack.get("raw_text", None)

        logger.info(
            f"[TTAF] pipeline=item_aware token->{self.score}->{self.smooth}(r={self.radius})->{self.agg} "
            f"item_len_scale={self.use_length_scale} "
            f"dominant_len_scale={self.dominant_length_scale} "
            f"dominant_select_mode={self.dominant_select_mode} "
            f"dominant_c={self.dominant_length_c if self.dominant_length_c_mode == 'fixed' else 'auto'} "
            f"hist_thr={thr:.6f} removed={int(preds.sum())}/{len(preds)}"
        )

        if true_labels is not None and len(true_labels) == len(preds):
            p = precision_score(true_labels, preds, average=None, zero_division=0)
            r = recall_score(true_labels, preds, average=None, zero_division=0)
            f1 = f1_score(true_labels, preds, average=None, zero_division=0)

            logger.info(f"[TTAF] precision of clean and poison: {np.around(p * 100, 2)}")
            logger.info(f"[TTAF] recall of clean and poison: {np.around(r * 100, 2)}")
            logger.info(f"[TTAF] f1 of clean and poison: {np.around(f1 * 100, 2)}")

            if len(p) > 1:
                self.last_detect_precision = float(p[1])
                self.last_detect_recall = float(r[1])
                self.last_detect_f1 = float(f1[1])
            else:
                self.last_detect_precision = float(p[0])
                self.last_detect_recall = float(r[0])
                self.last_detect_f1 = float(f1[0])

            self.last_detect_result = {
                "precision_clean": float(p[0]) if len(p) > 0 else None,
                "recall_clean": float(r[0]) if len(r) > 0 else None,
                "f1_clean": float(f1[0]) if len(f1) > 0 else None,
                "precision_poison": float(p[1]) if len(p) > 1 else None,
                "recall_poison": float(r[1]) if len(r) > 1 else None,
                "f1_poison": float(f1[1]) if len(f1) > 1 else None,
            }

        self._log_and_save(
            lengths=lengths,
            final_score=final_score.astype(np.float32),
            remove_idx=remove_idx,
            preds=preds,
            true_labels=true_labels,
            raw_text_payload=raw_text_payload,
            item_counts=item_counts,
            final_threshold=float(thr),
            feature_pack=feature_pack,
            mode=f"item_aware_dominant_len_scaled_pipeline_{self.dominant_select_mode}",
        )
        return preds.tolist()

    # ------------------------- stage A: extract features only -------------------------

    @torch.no_grad()
    def _extract_features_only(
        self,
        model: Victim,
        dataset: Any,
    ) -> Dict[str, Any]:
        loader = getCasualDataloader(dataset, batch_size=self.batch_size, shuffle=False)
        model.eval()

        all_len: List[int] = []
        all_true: List[int] = []
        all_item_counts: List[int] = []

        all_sample_item_ent = []
        all_sample_item_mp = []
        all_sample_item_neglog_mp = []
        all_sample_item_stage1 = []
        all_sample_item_nll = []
        all_sample_item_valid_len = []

        all_context = [] if self.save_raw_text else None
        all_target_text = [] if self.save_raw_text else None
        all_poison_label_raw = [] if self.save_raw_text else None

        pbar = tqdm(loader, desc="[TTAF] Extracting features", leave=True, mininterval=1.0)

        with torch.inference_mode():
            for batch in pbar:
                if not isinstance(batch, dict):
                    raise ValueError("Expected dataloader batch to be a dict for item-aware TTAF.")

                batch_size_cur = self._infer_batch_size(batch)

                batch_targets = list(batch["target"]) if "target" in batch else [""] * batch_size_cur
                batch_contexts = list(batch["context"]) if "context" in batch else [""] * batch_size_cur

                if self.save_raw_text:
                    all_target_text.extend(batch_targets)
                    all_context.extend(batch_contexts)

                if "poison_label" in batch:
                    pl_raw = batch["poison_label"]
                    if torch.is_tensor(pl_raw):
                        vals = pl_raw.detach().cpu().tolist()
                    else:
                        vals = list(pl_raw)
                    all_true.extend(vals)
                    if self.save_raw_text:
                        all_poison_label_raw.extend(vals)

                owner_sample_idx = []
                flat_item_texts = []

                for i in range(batch_size_cur):
                    items_i = self._target_to_items(batch_targets[i])
                    all_item_counts.append(len(items_i))
                    for item_text in items_i:
                        owner_sample_idx.append(i)
                        flat_item_texts.append(item_text)

                batch_sample_item_ent = [[] for _ in range(batch_size_cur)]
                batch_sample_item_mp = [[] for _ in range(batch_size_cur)]
                batch_sample_item_neglog_mp = [[] for _ in range(batch_size_cur)]
                batch_sample_item_stage1 = [[] for _ in range(batch_size_cur)]
                batch_sample_item_nll = [[] for _ in range(batch_size_cur)]
                batch_sample_item_valid_len = [[] for _ in range(batch_size_cur)]
                batch_sample_max_len = [0 for _ in range(batch_size_cur)]

                if len(flat_item_texts) == 0:
                    for i in range(batch_size_cur):
                        all_sample_item_ent.append(batch_sample_item_ent[i])
                        all_sample_item_mp.append(batch_sample_item_mp[i])
                        all_sample_item_neglog_mp.append(batch_sample_item_neglog_mp[i])
                        all_sample_item_stage1.append(batch_sample_item_stage1[i])
                        all_sample_item_nll.append(batch_sample_item_nll[i])
                        all_sample_item_valid_len.append(batch_sample_item_valid_len[i])
                        all_len.append(batch_sample_max_len[i])
                    continue

                item_micro_batch_size = max(self.batch_size * self.item_micro_batch_mult, self.batch_size)

                for start in range(0, len(flat_item_texts), item_micro_batch_size):
                    end = min(start + item_micro_batch_size, len(flat_item_texts))
                    chunk_item_texts = flat_item_texts[start:end]
                    chunk_owner_idx = owner_sample_idx[start:end]

                    chunk_batch = self._build_flat_item_batch(
                        batch=batch,
                        owner_sample_idx=chunk_owner_idx,
                        item_texts=chunk_item_texts,
                    )

                    inputs, labels, attentionMask = model.process(chunk_batch)
                    lengths = self._get_lengths(inputs, attentionMask)

                    with self._amp_context():
                        out = self._forward_logits_only(model, inputs, labels, attentionMask)

                    logits = out.logits
                    dev = logits.device

                    if torch.is_tensor(labels) and labels.device != dev:
                        labels = labels.to(dev, non_blocking=True)
                    if attentionMask is not None and torch.is_tensor(attentionMask) and attentionMask.device != dev:
                        attentionMask = attentionMask.to(dev, non_blocking=True)

                    token_ent, token_mp, token_nll, valid_mask, _, _ = self._token_stats_by_mode(
                        logits, labels, attentionMask
                    )

                    chunk_size = len(chunk_item_texts)

                    for k in range(chunk_size):
                        sample_i = chunk_owner_idx[k]
                        cur_len = int(lengths[k]) if k < len(lengths) else 0
                        batch_sample_max_len[sample_i] = max(batch_sample_max_len[sample_i], cur_len)

                        valid_len = int(valid_mask[k].long().sum().detach().cpu().item())

                        if self.save_token_trace:
                            out_dtype = torch.float16 if self.token_trace_dtype == "float16" else torch.float32

                            if token_ent is not None:
                                ent_arr = token_ent[k][valid_mask[k]].detach().to(out_dtype).cpu().numpy()
                            else:
                                ent_arr = None

                            if token_mp is not None:
                                mp_arr = token_mp[k][valid_mask[k]].detach().to(out_dtype).cpu().numpy()
                            else:
                                mp_arr = None

                            if token_nll is not None:
                                nll_arr = token_nll[k][valid_mask[k]].detach().to(out_dtype).cpu().numpy()
                            else:
                                nll_arr = None

                            if mp_arr is not None:
                                neglog_mp_arr = (-np.log(np.clip(mp_arr.astype(np.float64), EPS, 1.0))).astype(
                                    np.float16 if self.token_trace_dtype == "float16" else np.float32
                                )
                            else:
                                neglog_mp_arr = None

                            if ent_arr is not None and mp_arr is not None:
                                stage1_arr = (
                                    ent_arr.astype(np.float64)
                                    - np.log(np.clip(mp_arr.astype(np.float64), EPS, 1.0))
                                ).astype(np.float16 if self.token_trace_dtype == "float16" else np.float32)
                            else:
                                stage1_arr = None
                        else:
                            ent_arr = None
                            mp_arr = None
                            neglog_mp_arr = None
                            stage1_arr = None
                            nll_arr = None

                        batch_sample_item_ent[sample_i].append(ent_arr)
                        batch_sample_item_mp[sample_i].append(mp_arr)
                        batch_sample_item_neglog_mp[sample_i].append(neglog_mp_arr)
                        batch_sample_item_stage1[sample_i].append(stage1_arr)
                        batch_sample_item_nll[sample_i].append(nll_arr)
                        batch_sample_item_valid_len[sample_i].append(valid_len)

                for i in range(batch_size_cur):
                    all_sample_item_ent.append(batch_sample_item_ent[i])
                    all_sample_item_mp.append(batch_sample_item_mp[i])
                    all_sample_item_neglog_mp.append(batch_sample_item_neglog_mp[i])
                    all_sample_item_stage1.append(batch_sample_item_stage1[i])
                    all_sample_item_nll.append(batch_sample_item_nll[i])
                    all_sample_item_valid_len.append(batch_sample_item_valid_len[i])
                    all_len.append(batch_sample_max_len[i])

        lengths_np = np.asarray(all_len, dtype=np.int32)
        item_counts_np = np.asarray(all_item_counts, dtype=np.int32)

        true_labels = None
        if len(all_true) == len(lengths_np) and len(all_true) > 0:
            true_labels = np.asarray(all_true, dtype=int)

        raw_text_payload = None
        if self.save_raw_text:
            raw_text_payload = {
                "context": all_context,
                "target": all_target_text,
                "poison_label": all_poison_label_raw,
            }

        flat_valid_lens = []
        for sample_lens in all_sample_item_valid_len:
            flat_valid_lens.extend(sample_lens)

        auto_length_c = self._estimate_length_c(
            np.asarray(flat_valid_lens, dtype=np.int32)
        ) if self.use_length_scale else None

        dominant_auto_c = self._estimate_dominant_length_c(
            np.asarray(flat_valid_lens, dtype=np.int32)
        ) if self.dominant_length_scale else None

        feature_pack = {
            "defender": "leaf",
            "mode": "feature_extraction_only_item_aware",
            "true_labels": true_labels,
            "dataset": self.targetDataset,
            "poisoner_name": self.poisoner_name,
            "poisoner_key": self.poisoner_key,
            "features": {
                "lengths": lengths_np,
                "item_counts": item_counts_np,
                "sample_item_token_entropies": all_sample_item_ent,
                "sample_item_token_maxprobs": all_sample_item_mp,
                "sample_item_token_neglog_maxprobs": all_sample_item_neglog_mp,
                "sample_item_token_stage1_scores": all_sample_item_stage1,
                "sample_item_token_nll_scores": all_sample_item_nll,
                "sample_item_valid_lens": all_sample_item_valid_len,
            },
            "config": {
                "batch_size": self.batch_size,
                "save_token_trace": self.save_token_trace,
                "token_trace_dtype": self.token_trace_dtype,
                "token_trace_max_samples": self.token_trace_max_samples,
                "save_raw_text": self.save_raw_text,
                "save_global_stats": self.save_global_stats,
                "score": self.score,
                "smooth": self.smooth,
                "radius": self.radius,
                "agg": self.agg,
                "item_aware": self.item_aware,
                "item_micro_batch_mult": self.item_micro_batch_mult,
                "use_length_scale": self.use_length_scale,
                "length_c_mode": self.length_c_mode,
                "length_c": self.length_c,
                "length_c_quantile": self.length_c_quantile,
                "auto_length_c": auto_length_c,
                "dominant_length_scale": self.dominant_length_scale,
                "dominant_length_c_mode": self.dominant_length_c_mode,
                "dominant_length_c": self.dominant_length_c,
                "dominant_length_c_quantile": self.dominant_length_c_quantile,
                "dominant_auto_length_c": dominant_auto_c,
                "dominant_select_mode": self.dominant_select_mode,
                "count_mode": self.count_mode,
                "item_norm": self.item_norm,
                "hist_bins": self.hist_bins,
                "hist_smooth_radius": self.hist_smooth_radius,
                "use_amp": self.use_amp,
                "amp_dtype": self.amp_dtype,
                "always_save_all_token_stats": self.always_save_all_token_stats,
            },
        }

        if raw_text_payload is not None:
            feature_pack["raw_text"] = raw_text_payload

        if self.save_artifacts:
            fpath = os.path.join(self.run_dir, "leaf_features_only.pkl")
            with open(fpath, "wb") as f:
                pickle.dump(feature_pack, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"[TTAF] saved feature-only artifacts to {fpath}")

        return feature_pack

    # ------------------------- stage B: filter from features only -------------------------

    def _filter_from_features(
        self,
        feature_pack: Dict[str, Any],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        feats = feature_pack["features"]
        cfg = feature_pack["config"]

        sample_item_ent = feats.get("sample_item_token_entropies", None)
        sample_item_mp = feats.get("sample_item_token_maxprobs", None)
        sample_item_nll = feats.get("sample_item_token_nll_scores", None)
        sample_item_valid_lens = feats.get("sample_item_valid_lens", None)

        if sample_item_valid_lens is None:
            raise ValueError("sample_item_valid_lens is required for item-aware TTAF.")

        n_samples = len(sample_item_valid_lens)

        if self.score == "ent_only":
            if sample_item_ent is None:
                raise ValueError("sample_item_token_entropies is required for score='ent_only'.")
        elif self.score == "neglog_mp":
            if sample_item_mp is None:
                raise ValueError("sample_item_token_maxprobs is required for score='neglog_mp'.")
        elif self.score == "stage1":
            if sample_item_ent is None or sample_item_mp is None:
                raise ValueError("Both item entropies and item maxprobs are required for score='stage1'.")
        elif self.score == "nll":
            if sample_item_nll is None:
                raise ValueError(
                    "sample_item_token_nll_scores is required for score='nll'. "
                    "Please re-run feature extraction with the NLL-enabled TTAFDefender."
                )
        else:
            raise ValueError(f"Unknown score: {self.score}")

        item_c_value = cfg.get("auto_length_c", None)
        if self.use_length_scale and item_c_value is None:
            flat_valid_lens = []
            for xs in sample_item_valid_lens:
                flat_valid_lens.extend(xs)
            item_c_value = self._estimate_length_c(np.asarray(flat_valid_lens, dtype=np.int32))

        dom_c_value = cfg.get("dominant_auto_length_c", None)
        if self.dominant_length_scale and dom_c_value is None:
            flat_valid_lens = []
            for xs in sample_item_valid_lens:
                flat_valid_lens.extend(xs)
            dom_c_value = self._estimate_dominant_length_c(np.asarray(flat_valid_lens, dtype=np.int32))

        final_scores = []
        item_counts = []
        per_sample_item_scores = []
        per_sample_scaled_item_scores = []
        per_sample_top1_len = []
        per_sample_top1_idx = []

        for i in range(n_samples):
            ent_items = sample_item_ent[i] if sample_item_ent is not None else [None] * len(sample_item_valid_lens[i])
            mp_items = sample_item_mp[i] if sample_item_mp is not None else [None] * len(sample_item_valid_lens[i])
            nll_items = sample_item_nll[i] if sample_item_nll is not None else [None] * len(sample_item_valid_lens[i])
            valid_lens_i = np.asarray(sample_item_valid_lens[i], dtype=np.int32)

            item_scores_i = []

            for ent_j, mp_j, nll_j, valid_len_j in zip(ent_items, mp_items, nll_items, valid_lens_i):
                token_score = self._build_token_score(ent_j, mp_j, nll_j)

                if self.smooth == "tri" and self.radius > 0:
                    token_score = self._smooth_1d(token_score, self.radius)
                elif self.smooth == "none":
                    pass
                else:
                    raise ValueError(f"Unknown smooth mode: {self.smooth}")

                s_item = self._aggregate(token_score, self.agg)

                if self.use_length_scale and item_c_value is not None:
                    s_item = self._apply_length_scale(s_item, int(valid_len_j), float(item_c_value))

                item_scores_i.append(float(s_item))

            item_scores_i = np.asarray(item_scores_i, dtype=np.float64)

            if item_scores_i.size == 0:
                s_sample = 0.0
                top1_len = 0
                top1_idx = -1
                scaled_item_scores_i = item_scores_i.copy()
            else:
                # Raw item scores after token smoothing/aggregation and optional item-level length scale.
                scaled_item_scores_i = item_scores_i.copy()

                # dominant length scale is intended to suppress very short noisy items.
                # post_scale: old/default logic, select raw top1 first, then scale the selected item.
                # pre_scale : new logic, scale every item first, then select the dominant item.
                if self.dominant_length_scale and dom_c_value is not None:
                    scaled_item_scores_i = np.asarray(
                        [
                            self._apply_length_scale(
                                float(s_item),
                                int(valid_len_j),
                                float(dom_c_value),
                            )
                            for s_item, valid_len_j in zip(item_scores_i, valid_lens_i)
                        ],
                        dtype=np.float64,
                    )

                if self.dominant_select_mode == "pre_scale":
                    top1_idx = int(np.argmax(scaled_item_scores_i))
                    s_sample = float(scaled_item_scores_i[top1_idx])
                    top1_len = int(valid_lens_i[top1_idx])

                elif self.dominant_select_mode == "post_scale":
                    top1_idx = int(np.argmax(item_scores_i))
                    s_sample = float(item_scores_i[top1_idx])
                    top1_len = int(valid_lens_i[top1_idx])

                    if self.dominant_length_scale and dom_c_value is not None:
                        s_sample = self._apply_length_scale(
                            s_sample,
                            top1_len,
                            float(dom_c_value),
                        )
                else:
                    raise ValueError(f"Unknown dominant_select_mode: {self.dominant_select_mode}")

            final_scores.append(s_sample)
            item_counts.append(max(1, len(item_scores_i)))
            per_sample_item_scores.append(item_scores_i.tolist())
            per_sample_scaled_item_scores.append(scaled_item_scores_i.tolist())
            per_sample_top1_len.append(top1_len)
            per_sample_top1_idx.append(top1_idx)

        final_scores = np.asarray(final_scores, dtype=np.float64)
        item_counts = np.asarray(item_counts, dtype=np.int32)
        per_sample_top1_len = np.asarray(per_sample_top1_len, dtype=np.int32)
        per_sample_top1_idx = np.asarray(per_sample_top1_idx, dtype=np.int32)

        thr = self._hist_valley_threshold(final_scores)
        preds = (final_scores >= thr).astype(np.int32)

        cap = int(round(self.max_remove_ratio * len(final_scores)))
        cap = max(1, min(cap, len(final_scores)))
        if int(preds.sum()) > cap:
            order = np.argsort(final_scores)[::-1]
            capped = np.zeros_like(preds)
            capped[order[:cap]] = 1
            preds = capped
            logger.info(f"[TTAF] hist threshold exceeded cap, fallback to top-{cap} by final score.")

        remove_idx = np.where(preds == 1)[0].astype(np.int64)

        feature_pack["features"]["final_score"] = final_scores.astype(np.float32)
        feature_pack["features"]["item_counts"] = item_counts
        feature_pack["features"]["per_sample_item_scores"] = per_sample_item_scores
        feature_pack["features"]["per_sample_scaled_item_scores"] = per_sample_scaled_item_scores
        feature_pack["features"]["per_sample_top1_len"] = per_sample_top1_len
        feature_pack["features"]["per_sample_top1_idx"] = per_sample_top1_idx
        feature_pack["config"]["auto_length_c"] = item_c_value
        feature_pack["config"]["dominant_auto_length_c"] = dom_c_value
        feature_pack["config"]["dominant_select_mode"] = self.dominant_select_mode
        feature_pack["config"]["final_threshold"] = float(thr)

        return preds, remove_idx, final_scores.astype(np.float32), float(thr)

    # ------------------------- helpers -------------------------

    def _infer_batch_size(self, batch: Dict[str, Any]) -> int:
        for v in batch.values():
            if torch.is_tensor(v):
                return int(v.shape[0])
            if isinstance(v, (list, tuple)):
                return len(v)
        raise ValueError("Cannot infer batch size from batch.")

    def _target_to_items(self, target) -> List[str]:
        # main path: poisoner already normalizes target to List[str]
        if isinstance(target, list):
            items = [str(x).strip() for x in target if str(x).strip() != ""]
            return items if len(items) > 0 else [""]

        # fallback for old cached data
        text = str(target).strip()
        return [text] if text != "" else [""]

    def _build_flat_item_batch(
        self,
        batch: Dict[str, Any],
        owner_sample_idx: List[int],
        item_texts: List[str],
    ) -> Dict[str, Any]:
        if len(owner_sample_idx) != len(item_texts):
            raise ValueError("owner_sample_idx and item_texts must have the same length.")

        out = {}
        for k, v in batch.items():
            if k == "target":
                out[k] = list(item_texts)
                continue

            if torch.is_tensor(v):
                idx_tensor = torch.tensor(owner_sample_idx, device=v.device, dtype=torch.long)
                out[k] = v.index_select(0, idx_tensor)
            elif isinstance(v, (list, tuple)):
                out[k] = [v[i] for i in owner_sample_idx]
            else:
                out[k] = v
        return out

    def _item_count_from_target(self, target):
        if isinstance(target, list):
            return max(1, len(target))

        text = str(target)

        if self.count_mode == "list_only":
            return 1

        if self.count_mode == "semicolon":
            if ";" in text:
                parts = [x.strip() for x in text.split(";") if x.strip()]
                return max(1, len(parts))
            return 1

        if self.count_mode == "auto":
            cnt = 1
            if ";" in text:
                parts = [x.strip() for x in text.split(";") if x.strip()]
                cnt = max(cnt, len(parts))
            return max(1, cnt)

        raise ValueError(f"Unknown count_mode: {self.count_mode}")

    def _build_token_score(
        self,
        ent: Optional[np.ndarray],
        mp: Optional[np.ndarray],
        nll: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        if self.score == "ent_only":
            if ent is None:
                raise ValueError("ent is required for score='ent_only'")
            ent = np.asarray(ent, dtype=np.float64)
            return ent

        if self.score == "neglog_mp":
            if mp is None:
                raise ValueError("mp is required for score='neglog_mp'")
            mp = np.asarray(mp, dtype=np.float64)
            return -np.log(np.clip(mp, EPS, 1.0))

        if self.score == "stage1":
            if ent is None or mp is None:
                raise ValueError("Both ent and mp are required for score='stage1'")
            ent = np.asarray(ent, dtype=np.float64)
            mp = np.asarray(mp, dtype=np.float64)
            return ent - np.log(np.clip(mp, EPS, 1.0))

        if self.score == "nll":
            if nll is None:
                raise ValueError("nll is required for score='nll'")
            return np.asarray(nll, dtype=np.float64)

        raise ValueError(f"Unknown score: {self.score}")

    def _triangular_kernel(self, radius: int) -> np.ndarray:
        if radius <= 0:
            return np.array([1.0], dtype=np.float64)
        w = np.arange(1, radius + 2, dtype=np.float64)
        w = np.concatenate([w, w[-2::-1]])
        return w / w.sum()

    def _smooth_1d(self, arr: np.ndarray, radius: int) -> np.ndarray:
        arr = np.asarray(arr, dtype=np.float64)
        if arr.size == 0 or radius <= 0:
            return arr.copy()
        k = self._triangular_kernel(radius)
        pad = len(k) // 2
        x = np.pad(arr, (pad, pad), mode="edge")
        return np.convolve(x, k, mode="valid")

    def _aggregate(self, arr: np.ndarray, agg: str) -> float:
        arr = np.asarray(arr, dtype=np.float64)
        if arr.size == 0:
            return 0.0
        if agg == "max":
            return float(np.max(arr))
        if agg == "mean":
            return float(np.mean(arr))
        if agg == "top2":
            k = min(2, arr.size)
            return float(np.mean(np.partition(arr, -k)[-k:]))
        if agg == "top3":
            k = min(3, arr.size)
            return float(np.mean(np.partition(arr, -k)[-k:]))
        if agg == "top5":
            k = min(5, arr.size)
            return float(np.mean(np.partition(arr, -k)[-k:]))
        raise ValueError(f"Unknown agg: {agg}")

    def _apply_length_scale(self, score: float, valid_len: int, c: float) -> float:
        return float(score * min(1.0, float(valid_len) / float(c)))

    def _apply_item_norm(self, score: float, item_count: int) -> float:
        m = max(1, int(item_count))
        if self.item_norm == "none":
            return float(score)
        if self.item_norm == "sqrt":
            return float(score / math.sqrt(m))
        if self.item_norm == "linear":
            return float(score / m)
        if self.item_norm == "log":
            return float(score / max(math.log1p(m), 1.0))
        raise ValueError(f"Unknown item_norm: {self.item_norm}")

    def _estimate_length_c(self, valid_lens: np.ndarray) -> float:
        x = np.asarray(valid_lens, dtype=np.float64)
        x = x[np.isfinite(x)]
        x = x[x > 0]
        if x.size == 0:
            return 1.0
        if self.length_c_mode == "fixed":
            c = float(self.length_c)
        elif self.length_c_mode == "median":
            c = float(np.median(x))
        elif self.length_c_mode == "mean":
            c = float(np.mean(x))
        elif self.length_c_mode == "quantile":
            c = float(np.quantile(x, self.length_c_quantile))
        else:
            raise ValueError(f"Unknown length_c_mode: {self.length_c_mode}")
        return max(c, 1.0)

    def _estimate_dominant_length_c(self, valid_lens: np.ndarray) -> float:
        x = np.asarray(valid_lens, dtype=np.float64)
        x = x[np.isfinite(x)]
        x = x[x > 0]
        if x.size == 0:
            return 1.0

        if self.dominant_length_c_mode == "fixed":
            c = float(self.dominant_length_c)
        elif self.dominant_length_c_mode == "median":
            c = float(np.median(x))
        elif self.dominant_length_c_mode == "mean":
            c = float(np.mean(x))
        elif self.dominant_length_c_mode == "quantile":
            c = float(np.quantile(x, self.dominant_length_c_quantile))
        else:
            raise ValueError(f"Unknown dominant_length_c_mode: {self.dominant_length_c_mode}")

        return max(c, 1.0)

    def _moving_average(self, x: np.ndarray, radius: int) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if radius <= 0 or x.size == 0:
            return x.copy()
        k = np.ones(2 * radius + 1, dtype=np.float64)
        k = k / k.sum()
        return np.convolve(x, k, mode="same")

    def _find_local_peaks(self, y: np.ndarray) -> List[int]:
        y = np.asarray(y, dtype=np.float64)
        if y.size < 3:
            return []
        peaks = []
        for i in range(1, len(y) - 1):
            if y[i] > y[i - 1] and y[i] >= y[i + 1]:
                peaks.append(i)
        return peaks

    def _hist_valley_threshold(self, scores: np.ndarray) -> float:
        """
        Final histogram threshold:
        1. Build histogram of sample-level scores.
        2. Smooth histogram counts with moving average.
        3. Select the leftmost local peak as the clean peak.
        4. Select the highest local peak on the right side as the suspicious peak.
        5. Find the low-density valley between the two peaks.
        6. If the valley forms a low-density plateau, use the right edge of the plateau as threshold.

        This version removes:
        - min_peak_ratio
        - q80 candidate constraint
        - distance_weight
        - q70 floor
        """

        x = np.asarray(scores, dtype=np.float64)

        if x.size < 10:
            thr = float(np.median(x))
            logger.info(
                f"[TTAF] hist threshold fallback=small_n -> median thr={thr:.6f}"
            )
            return thr

        lo = float(np.min(x))
        hi = float(np.max(x))

        if (not np.isfinite(lo)) or (not np.isfinite(hi)) or lo == hi:
            thr = float(np.median(x))
            logger.info(
                f"[TTAF] hist threshold fallback=bad_range -> median thr={thr:.6f}"
            )
            return thr

        # ------------------------------------------------------------------
        # 1. Histogram + smoothing
        # ------------------------------------------------------------------
        counts, bin_edges = np.histogram(
            x,
            bins=self.hist_bins,
            range=(lo, hi),
        )
        centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        smooth_counts = self._moving_average(
            counts.astype(np.float64),
            self.hist_smooth_radius,
        )

        # ------------------------------------------------------------------
        # 2. Find local peaks
        # ------------------------------------------------------------------
        peaks = self._find_local_peaks(smooth_counts)

        if len(peaks) == 0:
            thr = float(np.median(x))
            logger.info(
                f"[TTAF] hist threshold fallback=no_peaks -> median thr={thr:.6f}"
            )
            return thr

        # ------------------------------------------------------------------
        # 3. Clean peak = leftmost peak
        # ------------------------------------------------------------------
        clean_peak = int(min(peaks))

        # ------------------------------------------------------------------
        # 4. Right peak = highest local peak sufficiently far from clean peak
        # ------------------------------------------------------------------
        min_gap_bins = max(3, int(round(self.hist_bins * 0.06)))

        right_candidates = [
            int(p) for p in peaks
            if p > clean_peak + min_gap_bins
        ]

        if len(right_candidates) == 0:
            # Conservative fallback: search the lowest point on the far-right side.
            start = min(
                len(centers) - 1,
                clean_peak + max(min_gap_bins, self.hist_bins // 8),
            )

            if start < len(centers) - 1:
                valley_idx = start + int(np.argmin(smooth_counts[start:]))
                thr = float(centers[valley_idx])

                logger.info(
                    f"[TTAF] hist threshold mode=far_right_valley "
                    f"clean_peak={clean_peak} valley={valley_idx} "
                    f"thr={thr:.6f}"
                )
                return thr

            thr = float(np.median(x))
            logger.info(
                f"[TTAF] hist threshold fallback=no_right_peak -> median thr={thr:.6f}"
            )
            return thr

        right_peak = int(max(right_candidates, key=lambda p: smooth_counts[p]))

        # ------------------------------------------------------------------
        # 5. Find valley between clean peak and right peak
        # ------------------------------------------------------------------
        l, r = sorted([clean_peak, right_peak])
        valley_region = smooth_counts[l:r + 1]

        valley_left_idx = l + int(np.argmin(valley_region))
        valley_min = float(smooth_counts[valley_left_idx])

        # ------------------------------------------------------------------
        # 6. Valley plateau right-edge refinement
        # ------------------------------------------------------------------
        # The low-density separation may be a flat plateau rather than a single point.
        # We use the right edge of this low-density plateau as the threshold.
        clean_peak_height = float(smooth_counts[clean_peak])
        right_peak_height = float(smooth_counts[right_peak])

        plateau_eps_rel = getattr(self, "plateau_eps_rel", 0.01)
        rise_patience = getattr(self, "rise_patience", 2)

        plateau_eps = max(
            1e-12,
            plateau_eps_rel * min(clean_peak_height, right_peak_height),
        )

        valley_idx = valley_left_idx

        for j in range(valley_left_idx, r + 1):
            if smooth_counts[j] <= valley_min + plateau_eps:
                valley_idx = int(j)
                continue

            # Once the curve leaves the low-density plateau and stays above it
            # for a few bins, we stop at the last low-density bin.
            end = min(r + 1, j + rise_patience + 1)
            if np.all(smooth_counts[j:end] > valley_min + plateau_eps):
                break

        thr = float(centers[valley_idx])

        logger.info(
            f"[TTAF] hist threshold mode=valley_right_edge "
            f"clean_peak={clean_peak} right_peak={right_peak} "
            f"valley_left={valley_left_idx} valley_right={valley_idx} "
            f"min_gap_bins={min_gap_bins} "
            f"plateau_eps_rel={plateau_eps_rel:.4f} "
            f"rise_patience={rise_patience} "
            f"thr={thr:.6f}"
        )

        return thr

    # ------------------------- forward / stats -------------------------

    def _amp_context(self):
        if not (self.use_amp and torch.cuda.is_available()):
            return nullcontext()
        amp_dtype = torch.bfloat16 if self.amp_dtype == "bfloat16" else torch.float16
        return torch.autocast(device_type="cuda", dtype=amp_dtype)

    def _forward_logits_only(self, model, inputs, labels, attentionMask):
        try:
            return model.forward(
                inputs=inputs,
                labels=labels,
                attentionMask=attentionMask,
                output_hidden_states=False,
            )
        except TypeError:
            return model.forward(inputs=inputs, labels=labels, attentionMask=attentionMask)

    def _token_stats_by_mode(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        attention_mask: Optional[torch.Tensor],
        eps: float = 1e-12,
    ):
        if logits.dim() != 3:
            raise ValueError("Expected seq logits with shape [B, L, V].")

        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = labels[:, 1:].contiguous()
        ignore = shift_labels.eq(IGNORE_INDEX)

        if attention_mask is not None:
            valid_mask = attention_mask[:, 1:].contiguous().bool()
            valid_mask = valid_mask & (~ignore)
        else:
            valid_mask = ~ignore

        denom = valid_mask.float().sum(dim=1).clamp(min=1.0)

        x = shift_logits.float()
        log_probs = torch.log_softmax(x, dim=-1)
        probs = torch.exp(log_probs)

        # Always compute entropy, maxprob, and gold-label NLL so that all
        # ablation scores can be reconstructed offline from a single pkl.
        token_ent = -(probs * log_probs).sum(dim=-1)
        token_mp = probs.max(dim=-1).values

        # Gather p(y_t | y_<t, x) on the teacher-forced target path.
        # Invalid/ignored labels are temporarily mapped to 0 only to keep
        # torch.gather in range; they are masked out immediately afterwards.
        safe_labels = shift_labels.masked_fill(ignore, 0)
        token_logp_gold = log_probs.gather(
            dim=-1,
            index=safe_labels.unsqueeze(-1),
        ).squeeze(-1)
        token_nll = -token_logp_gold

        token_ent = token_ent.masked_fill(~valid_mask, 0.0)
        token_mp = token_mp.masked_fill(~valid_mask, 0.0)
        token_nll = token_nll.masked_fill(~valid_mask, 0.0)

        mean_ent = (token_ent * valid_mask.float()).sum(dim=1) / denom
        mean_mp = (token_mp * valid_mask.float()).sum(dim=1) / denom

        return token_ent, token_mp, token_nll, valid_mask, mean_ent, mean_mp

    def _get_lengths(self, inputs, attention_mask) -> List[int]:
        if attention_mask is not None and torch.is_tensor(attention_mask):
            return attention_mask.detach().cpu().sum(dim=1).int().tolist()
        if torch.is_tensor(inputs):
            return [inputs.shape[1]] * inputs.shape[0]
        return [0] * (len(inputs) if hasattr(inputs, "__len__") else 0)

    # ------------------------- filtering -------------------------

    def _filter_by_preds(self, data: Any, preds: List[int]):
        preds_np = np.array(preds, dtype=int)
        keep_idx = np.where(preds_np == 0)[0].astype(np.int64)
        if isinstance(data, Dataset):
            return Subset(data, keep_idx.tolist())
        if hasattr(data, "__len__") and hasattr(data, "__getitem__"):
            return [data[i] for i in keep_idx.tolist()]
        raise TypeError(f"Unsupported poison_data type: {type(data)}")

    # ------------------------- saving -------------------------

    def _log_and_save(
        self,
        lengths: np.ndarray,
        final_score: np.ndarray,
        remove_idx: np.ndarray,
        preds: np.ndarray,
        true_labels: Optional[np.ndarray],
        raw_text_payload: Optional[Dict[str, Any]],
        item_counts: np.ndarray,
        final_threshold: float,
        feature_pack: Dict[str, Any],
        mode: str,
    ):
        n = len(lengths)
        removed = int(preds.sum())
        logger.info(
            f"[TTAF] summary: mode={mode} n={n}, removed={removed}, "
            f"score(min/med/max)={final_score.min():.4f}/{np.median(final_score):.4f}/{final_score.max():.4f}"
        )

        if not self.save_artifacts:
            return

        payload: Dict[str, Any] = {
            "defender": "leaf",
            "mode": mode,
            "true_labels": true_labels,
            "preds": preds.astype(np.int32),
            "remove_idx": remove_idx.astype(np.int64),
            "dataset": self.targetDataset,
            "poisoner_name": self.poisoner_name,
            "poisoner_key": self.poisoner_key,
            "features": {
                "lengths": lengths.astype(np.int32),
                "final_score": final_score.astype(np.float32),
                "item_counts": item_counts.astype(np.int32),
                "sample_item_token_entropies": feature_pack["features"].get("sample_item_token_entropies", None),
                "sample_item_token_maxprobs": feature_pack["features"].get("sample_item_token_maxprobs", None),
                "sample_item_token_neglog_maxprobs": feature_pack["features"].get("sample_item_token_neglog_maxprobs", None),
                "sample_item_token_stage1_scores": feature_pack["features"].get("sample_item_token_stage1_scores", None),
                "sample_item_token_nll_scores": feature_pack["features"].get("sample_item_token_nll_scores", None),
                "sample_item_valid_lens": feature_pack["features"].get("sample_item_valid_lens", None),
                "per_sample_item_scores": feature_pack["features"].get("per_sample_item_scores", None),
                "per_sample_scaled_item_scores": feature_pack["features"].get("per_sample_scaled_item_scores", None),
                "per_sample_top1_len": feature_pack["features"].get("per_sample_top1_len", None),
                "per_sample_top1_idx": feature_pack["features"].get("per_sample_top1_idx", None),
            },
            "config": {
                "unsupervised": True,
                "batch_size": self.batch_size,
                "min_dataset_size": self.min_dataset_size,
                "max_remove_ratio": self.max_remove_ratio,
                "score": self.score,
                "smooth": self.smooth,
                "radius": self.radius,
                "agg": self.agg,
                "item_aware": self.item_aware,
                "item_micro_batch_mult": self.item_micro_batch_mult,
                "use_length_scale": self.use_length_scale,
                "length_c_mode": self.length_c_mode,
                "length_c": self.length_c,
                "length_c_quantile": self.length_c_quantile,
                "auto_length_c": feature_pack["config"].get("auto_length_c", None),
                "dominant_length_scale": self.dominant_length_scale,
                "dominant_length_c_mode": self.dominant_length_c_mode,
                "dominant_length_c": self.dominant_length_c,
                "dominant_length_c_quantile": self.dominant_length_c_quantile,
                "dominant_auto_length_c": feature_pack["config"].get("dominant_auto_length_c", None),
                "count_mode": self.count_mode,
                "item_norm": self.item_norm,
                "hist_bins": self.hist_bins,
                "hist_smooth_radius": self.hist_smooth_radius,
                "final_threshold": float(final_threshold),
                "save_token_trace": self.save_token_trace,
                "save_raw_text": self.save_raw_text,
                "save_global_stats": self.save_global_stats,
                "use_amp": self.use_amp,
                "amp_dtype": self.amp_dtype,
                "always_save_all_token_stats": getattr(self, "always_save_all_token_stats", True),
            },
        }

        if raw_text_payload is not None:
            payload["raw_text"] = raw_text_payload

        fpath = os.path.join(self.run_dir, "leaf_features.pkl")
        with open(fpath, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"[TTAF] saved artifacts to {fpath}")

# Backward-compatible class alias for old scripts/configurations.
LEAFDefender = TTAFDefender
