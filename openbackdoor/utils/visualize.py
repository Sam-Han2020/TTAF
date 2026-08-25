import os
import sys
import json


def result_visualizer(result):
    stream_writer = sys.stdout.write
    try:
        cols = os.get_terminal_size().columns
    except OSError:
        cols = 80

    left = []
    right = []
    for key, val in result.items():
        left.append(" " + str(key) + ": ")
        if isinstance(val, bool):
            right.append(" yes" if val else " no")
        elif isinstance(val, int):
            right.append(" %d" % val)
        elif isinstance(val, float):
            right.append(" %.4g" % val)
        else:
            right.append(" %s" % str(val))
        right[-1] += " "

    if len(left) == 0:
        return

    max_left = max(list(map(len, left)))
    max_right = max(list(map(len, right)))
    if max_left + max_right + 3 > cols:
        delta = max_left + max_right + 3 - cols
        if delta % 2 == 1:
            delta -= 1
            max_left -= 1
        max_left -= delta // 2
        max_right -= delta // 2

    max_left = max(10, max_left)
    max_right = max(10, max_right)
    total = max_left + max_right + 3

    title = "Summary"
    if total - 2 < len(title):
        title = title[:total - 2]
    offtitle = ((total - len(title)) // 2) - 1
    stream_writer("+" + ("=" * (total - 2)) + "+\n")
    stream_writer("|" + " " * offtitle + title + " " * (total - 2 - offtitle - len(title)) + "|" + "\n")
    stream_writer("+" + ("=" * (total - 2)) + "+\n")
    for l, r in zip(left, right):
        l = l[:max_left]
        r = r[:max_right]
        l += " " * (max_left - len(l))
        r += " " * (max_right - len(r))
        stream_writer("|" + l + "|" + r + "|" + "\n")
    stream_writer("+" + ("=" * (total - 2)) + "+\n")


def _safe_max_metric(results, split_type, metric_name):
    vals = []
    for k, v in results.items():
        if not isinstance(v, dict):
            continue
        parts = k.split("-")
        if len(parts) >= 2 and parts[1] == split_type:
            metric_val = v.get(metric_name)
            if metric_val is not None:
                vals.append(metric_val)
    return max(vals) if len(vals) > 0 else None


def build_display_result(config, results, extra_result=None):
    poisoner_cfg = config['attacker']['poisoner']

    poisoner = poisoner_cfg.get('name')
    poison_rate = poisoner_cfg.get('poison_rate')
    label_consistency = poisoner_cfg.get('label_consistency')
    label_dirty = poisoner_cfg.get('label_dirty')
    target_label = poisoner_cfg.get('target_label')
    attack_mode = poisoner_cfg.get('attack_mode', 'unknown')

    poison_dataset = config['poison_dataset']['name']
    method = config.get("defender", {}).get("name", "no_defender")

    CACC = results['test-clean']['accuracy']
    CEMR = results['test-clean'].get("emr")
    CKMR = results['test-clean'].get("kmr")

    if 'test-poison' in results:
        ASR = results['test-poison']['accuracy']
        BEMR = results['test-poison'].get("emr")
        BKMR = results['test-poison'].get("kmr")
    else:
        ASR = _safe_max_metric(results, "poison", "accuracy")
        BEMR = _safe_max_metric(results, "poison", "emr")
        BKMR = _safe_max_metric(results, "poison", "kmr")

    PPL = results.get("ppl")
    GE = results.get("grammar")
    USE = results.get("use")

    display_result = {
        "method": method,
        "poison_dataset": poison_dataset,
        "poisoner": poisoner,
        "attack_mode": attack_mode,
        "poison_rate": poison_rate,
        "label_consistency": label_consistency,
        "label_dirty": label_dirty,
        "target_label": target_label,
        "CACC": CACC,
        "ASR": ASR,
        "ΔPPL": PPL,
        "ΔGE": GE,
        "USE": USE,
        "CEMR": CEMR,
        "CKMR": CKMR,
        "BEMR": BEMR,
        "BKMR": BKMR,
    }

    if extra_result is not None and isinstance(extra_result, dict):
        display_result.update(extra_result)

    return display_result


def save_display_result_txt(display_result, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        for k, v in display_result.items():
            f.write(f"{k}: {v}\n")


def save_display_result_json(display_result, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(display_result, f, indent=4, ensure_ascii=False)


def display_results(config, results, save_dir=None, extra_result=None):
    """
    作用：
    1. 打印 summary
    2. 返回可保存的 display_result
    3. 若提供 save_dir，则自动保存 txt 和 json
    """
    display_result = build_display_result(config, results, extra_result=extra_result)

    result_visualizer(display_result)

    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
        save_display_result_txt(display_result, os.path.join(save_dir, "summary.txt"))
        save_display_result_json(display_result, os.path.join(save_dir, "summary.json"))

    return display_result