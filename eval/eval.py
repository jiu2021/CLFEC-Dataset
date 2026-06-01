#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI校对模型效果评估脚本
支持严格匹配和宽松匹配模式，计算检测和纠错指标

新增功能：
1) gold 中每个样例新增字段 "type"：
   - "fec_and_gec" / "fec_only" / "gec_only" / "no_error"
   => 分 type 计算检测&纠错指标

2) gold 的 cors 中新增字段 "error_type"：
   - "Word_Error" / "Fact_Error" / "Punc_Error" / "Grammar_Error"
   => 分 error_type 计算检测召回率（strict/loose 各一份）
"""

import json
import argparse
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
import os


SAMPLE_TYPES = ["fec_and_gec", "fec_only", "gec_only", "no_error"]
ERROR_TYPES = ["Word_Error", "Fact_Error", "Punc_Error", "Grammar_Error"]


def load_json_file(file_path: str) -> List[Dict]:
    """
    加载JSON文件，处理可能的格式问题
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 处理多个JSON数组拼接的情况 (如 ][][])
    content = content.replace('][', ',')

    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"文件路径: {file_path}")
        raise


def extract_cors_by_id(data: List[Dict]) -> Dict[int, List[Dict]]:
    """
    从数据中提取cors，按id分组
    返回: {id: [cors_list]}
    """
    cors_by_id = defaultdict(list)

    for item in data:
        item_id = item.get('id')
        cors = item.get('cors', [])

        if item_id is not None and cors:
            normalized_cors = []
            for cor in cors:
                if isinstance(cor, dict):
                    # 保留原字段（包含 error_type 等）
                    normalized_cors.append(cor)
                elif isinstance(cor, (list, tuple)) and len(cor) >= 4:
                    # (start, end, error_word, candidate_word, id)
                    normalized_cors.append({
                        'start': cor[0],
                        'end': cor[1],
                        'error_word': cor[2],
                        'candidate_word': cor[3],
                        'item_id': cor[4] if len(cor) > 4 else item_id
                    })

            cors_by_id[item_id].extend(normalized_cors)

    return dict(cors_by_id)


def extract_sample_type_by_id(gold_data: List[Dict]) -> Dict[int, str]:
    """
    从 gold 数据中提取每个 id 的 sample type
    """
    type_by_id = {}
    for item in gold_data:
        item_id = item.get("id")
        if item_id is None:
            continue
        t = item.get("type", "")
        # 兼容异常值：不在预期集合里就归为 "unknown"
        if t not in SAMPLE_TYPES:
            t = "unknown"
        type_by_id[item_id] = t
    return type_by_id


def group_ids_by_type(type_by_id: Dict[int, str]) -> Dict[str, Set[int]]:
    """
    把 id 按 type 分组
    """
    ids_by_type = defaultdict(set)
    for item_id, t in type_by_id.items():
        ids_by_type[t].add(item_id)

    # 确保四类都存在 key（即使为空）
    for t in SAMPLE_TYPES:
        ids_by_type.setdefault(t, set())
    if "unknown" in ids_by_type:
        ids_by_type.setdefault("unknown", set())

    return dict(ids_by_type)


def is_strict_match(pred_cor: Dict, gold_cor: Dict) -> bool:
    """
    严格匹配：start和end完全一致
    """
    return (pred_cor['start'] == gold_cor['start'] and
            pred_cor['end'] == gold_cor['end'])


def is_loose_match(pred_cor: Dict, gold_cor: Dict, overlap_threshold: float = 0.5) -> bool:
    """
    宽松匹配：允许一定范围重叠
    overlap_threshold: 重叠比例阈值，默认0.5表示重叠部分占较小区间的50%以上
    """
    pred_start, pred_end = pred_cor['start'], pred_cor['end']
    gold_start, gold_end = gold_cor['start'], gold_cor['end']

    overlap_start = max(pred_start, gold_start)
    overlap_end = min(pred_end, gold_end)

    if overlap_start >= overlap_end:
        return False

    overlap_len = overlap_end - overlap_start
    pred_len = pred_end - pred_start
    gold_len = gold_end - gold_start

    min_len = min(pred_len, gold_len)
    if min_len == 0:
        return False

    overlap_ratio = overlap_len / min_len
    return overlap_ratio >= overlap_threshold


def is_correction_match(pred_cor: Dict, gold_cor: Dict) -> bool:
    """
    判断纠错是否匹配：candidate_word一致
    """
    return pred_cor.get('candidate_word') == gold_cor.get('candidate_word')


def calculate_metrics(
    pred_cors_by_id: Dict[int, List[Dict]],
    gold_cors_by_id: Dict[int, List[Dict]],
    match_mode: str = 'strict',
    overlap_threshold: float = 0.5,
    id_filter: Optional[Set[int]] = None
) -> Dict:
    """
    计算检测和纠错指标 + 分 error_type 的检测召回率

    参数:
        id_filter: 只在这些 id 上计算（用于按 sample type 分组）
    """
    match_func = is_strict_match if match_mode == 'strict' else lambda p, g: is_loose_match(p, g, overlap_threshold)

    detection_tp = 0
    detection_fp = 0
    detection_fn = 0

    correction_tp = 0
    correction_fp = 0
    correction_fn = 0

    # error_type 统计（基于 gold，计算 detection recall）
    gold_total_by_error_type = defaultdict(int)
    gold_matched_by_error_type = defaultdict(int)

    all_ids = set(pred_cors_by_id.keys()) | set(gold_cors_by_id.keys())
    if id_filter is not None:
        all_ids = all_ids & set(id_filter)

    for item_id in all_ids:
        pred_cors = pred_cors_by_id.get(item_id, [])
        gold_cors = gold_cors_by_id.get(item_id, [])

        # 累计 gold error_type 总数
        for g in gold_cors:
            et = g.get("error_type", "UNKNOWN")
            gold_total_by_error_type[et] += 1

        matched_gold_indices = set()

        for pred_cor in pred_cors:
            detection_matched = False
            correction_matched = False

            for gold_idx, gold_cor in enumerate(gold_cors):
                if gold_idx in matched_gold_indices:
                    continue

                if match_func(pred_cor, gold_cor):
                    detection_matched = True
                    matched_gold_indices.add(gold_idx)

                    if is_correction_match(pred_cor, gold_cor):
                        correction_matched = True
                    break

            if detection_matched:
                detection_tp += 1
                if correction_matched:
                    correction_tp += 1
                else:
                    correction_fp += 1
            else:
                detection_fp += 1
                correction_fp += 1

        # 漏报
        unmatched_gold_count = len(gold_cors) - len(matched_gold_indices)
        detection_fn += unmatched_gold_count
        correction_fn += unmatched_gold_count

        # 匹配到的 gold 分 error_type 记数（每个 gold 最多被匹配一次）
        for idx in matched_gold_indices:
            et = gold_cors[idx].get("error_type", "UNKNOWN")
            gold_matched_by_error_type[et] += 1

    def safe_divide(numerator, denominator):
        return numerator / denominator if denominator > 0 else 0.0

    detection_precision = safe_divide(detection_tp, detection_tp + detection_fp)
    detection_recall = safe_divide(detection_tp, detection_tp + detection_fn)
    detection_f1 = safe_divide(2 * detection_precision * detection_recall, detection_precision + detection_recall)

    correction_precision = safe_divide(correction_tp, correction_tp + correction_fp)
    correction_recall = safe_divide(correction_tp, correction_tp + correction_fn)
    correction_f1 = safe_divide(2 * correction_precision * correction_recall, correction_precision + correction_recall)

    # 分 error_type 的 detection recall
    recall_by_error_type = {}
    for et in ERROR_TYPES:
        total = gold_total_by_error_type.get(et, 0)
        matched = gold_matched_by_error_type.get(et, 0)
        recall_by_error_type[et] = {
            "gold_total": total,
            "matched": matched,
            "recall": safe_divide(matched, total)
        }

    # 也把 UNKNOWN（如果存在）带上，方便你排查数据
    for et, total in list(gold_total_by_error_type.items()):
        if et in ERROR_TYPES:
            continue
        matched = gold_matched_by_error_type.get(et, 0)
        recall_by_error_type[et] = {
            "gold_total": total,
            "matched": matched,
            "recall": safe_divide(matched, total)
        }

    return {
        'match_mode': match_mode,
        'overlap_threshold': overlap_threshold if match_mode == 'loose' else None,
        'detection': {
            'true_positive': detection_tp,
            'false_positive': detection_fp,
            'false_negative': detection_fn,
            'precision': detection_precision,
            'recall': detection_recall,
            'f1_score': detection_f1
        },
        'correction': {
            'true_positive': correction_tp,
            'false_positive': correction_fp,
            'false_negative': correction_fn,
            'precision': correction_precision,
            'recall': correction_recall,
            'f1_score': correction_f1
        },
        'recall_by_error_type': recall_by_error_type
    }


def format_metrics_report(metrics: Dict, model_name: str, title_suffix: str = "") -> str:
    """
    格式化指标报告
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"模型评估报告: {model_name}{title_suffix}")
    lines.append("=" * 80)
    lines.append("")

    lines.append(f"匹配模式: {metrics['match_mode']}")
    if metrics['overlap_threshold'] is not None:
        lines.append(f"重叠阈值: {metrics['overlap_threshold']}")
    lines.append("")

    lines.append("-" * 80)
    lines.append("检测指标 (Detection Metrics)")
    lines.append("-" * 80)
    det = metrics['detection']
    lines.append(f"True Positive  (TP): {det['true_positive']:>6}")
    lines.append(f"False Positive (FP): {det['false_positive']:>6}")
    lines.append(f"False Negative (FN): {det['false_negative']:>6}")
    lines.append(f"Precision:           {det['precision']:>6.4f}")
    lines.append(f"Recall:              {det['recall']:>6.4f}")
    lines.append(f"F1-Score:            {det['f1_score']:>6.4f}")
    lines.append("")

    lines.append("-" * 80)
    lines.append("纠错指标 (Correction Metrics)")
    lines.append("-" * 80)
    cor = metrics['correction']
    lines.append(f"True Positive  (TP): {cor['true_positive']:>6}")
    lines.append(f"False Positive (FP): {cor['false_positive']:>6}")
    lines.append(f"False Negative (FN): {cor['false_negative']:>6}")
    lines.append(f"Precision:           {cor['precision']:>6.4f}")
    lines.append(f"Recall:              {cor['recall']:>6.4f}")
    lines.append(f"F1-Score:            {cor['f1_score']:>6.4f}")
    lines.append("")

    # 新增：分 error_type 的 recall
    lines.append("-" * 80)
    lines.append("分 error_type 的检测召回率 (Recall by cors.error_type, Detection)")
    lines.append("-" * 80)
    rbet = metrics.get("recall_by_error_type", {})
    # 固定顺序先输出四类
    for et in ERROR_TYPES:
        item = rbet.get(et, {"gold_total": 0, "matched": 0, "recall": 0.0})
        lines.append(f"{et:<14}  gold={item['gold_total']:>6}  hit={item['matched']:>6}  recall={item['recall']:.4f}")
    # 再输出其他未知类（如有）
    extra_types = [k for k in rbet.keys() if k not in ERROR_TYPES]
    if extra_types:
        lines.append("")
        lines.append("其他/未知 error_type：")
        for et in sorted(extra_types):
            item = rbet[et]
            lines.append(f"{et:<14}  gold={item['gold_total']:>6}  hit={item['matched']:>6}  recall={item['recall']:.4f}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='AI校对模型效果评估')
    parser.add_argument('--gold', type=str, default='./data/AI校对测试集-未标注.json',
                        help='标准答案文件路径')
    parser.add_argument('--pred', type=str, default='./data/Qwen3-8B-1024.json',
                        help='模型预测结果文件路径')
    parser.add_argument('--mode', type=str, choices=['strict', 'loose', 'both'],
                        default='both', help='匹配模式: strict(严格), loose(宽松), both(两者)')
    parser.add_argument('--overlap-threshold', type=float, default=0.5,
                        help='宽松匹配的重叠阈值 (0-1), 默认0.5')
    parser.add_argument('--output-dir', type=str, default='./data',
                        help='结果输出目录')
    parser.add_argument('--is_limit_range', action='store_true',
                        help='是否是限制范围测试集')
    args = parser.parse_args()

    print(f"加载标准答案文件: {args.gold}")
    gold_data = load_json_file(args.gold)
    print(f"标准答案数据条数: {len(gold_data)}")

    print(f"加载模型预测文件: {args.pred}")
    pred_data = load_json_file(args.pred)
    print(f"模型预测数据条数: {len(pred_data)}")

    print("\n提取错误数据...")
    gold_cors_by_id = extract_cors_by_id(gold_data)
    pred_cors_by_id = extract_cors_by_id(pred_data)

    # sample type 分组（基于 gold）
    type_by_id = extract_sample_type_by_id(gold_data)
    ids_by_type = group_ids_by_type(type_by_id)

    if args.is_limit_range:
        print("\n应用范围限制：仅保留与金标准区间有重叠的预测错误...")

        def has_overlap(p, g):
            return not (p['end'] <= g['start'] or p['start'] >= g['end'])

        filtered_pred = {}

        for item_id, pred_list in pred_cors_by_id.items():
            gold_list = gold_cors_by_id.get(item_id, [])
            if not gold_list:
                continue

            kept = []
            for p in pred_list:
                for g in gold_list:
                    if has_overlap(p, g):
                        kept.append(p)
                        break

            if kept:
                filtered_pred[item_id] = kept

        pred_cors_by_id = filtered_pred

        filtered_total = sum(len(v) for v in pred_cors_by_id.values())
        print(f"范围限制后预测错误总数: {filtered_total}")

    gold_total_errors = sum(len(cors) for cors in gold_cors_by_id.values())
    pred_total_errors = sum(len(cors) for cors in pred_cors_by_id.values())
    total_chars = sum(len(item.get("input_text", "")) for item in pred_data)

    print(f"标准答案错误总数: {gold_total_errors}")
    print(f"模型预测错误总数: {pred_total_errors}")
    print(f"输入总字数: {total_chars}")

    model_name = os.path.splitext(os.path.basename(args.pred))[0]

    results = []

    def run_and_print(match_mode: str, overlap_threshold: float):
        print(f"\n计算 {match_mode} 匹配指标...")

        # 1) overall
        overall = calculate_metrics(
            pred_cors_by_id,
            gold_cors_by_id,
            match_mode=match_mode,
            overlap_threshold=overlap_threshold
        )
        print(format_metrics_report(overall, model_name, title_suffix=" (Overall)"))

        # 2) by sample type
        by_sample_type = {}
        for t in SAMPLE_TYPES + (["unknown"] if "unknown" in ids_by_type else []):
            id_set = ids_by_type.get(t, set())
            m = calculate_metrics(
                pred_cors_by_id,
                gold_cors_by_id,
                match_mode=match_mode,
                overlap_threshold=overlap_threshold,
                id_filter=id_set
            )
            by_sample_type[t] = m
            print(format_metrics_report(m, model_name, title_suffix=f" (Type={t}, n={len(id_set)})"))

        pack = {
            "match_mode": match_mode,
            "overlap_threshold": overlap_threshold if match_mode == "loose" else None,
            "overall": overall,
            "by_sample_type": by_sample_type
        }
        results.append(pack)

    if args.mode in ['strict', 'both']:
        run_and_print("strict", args.overlap_threshold)

    if args.mode in ['loose', 'both']:
        run_and_print("loose", args.overlap_threshold)

    os.makedirs(args.output_dir, exist_ok=True)
    output_file = os.path.join(args.output_dir, f"{model_name}_详细评估结果.txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        for pack in results:
            match_mode = pack["match_mode"]
            overall = pack["overall"]
            f.write(format_metrics_report(overall, model_name, title_suffix=" (Overall)"))
            f.write("\n")

            for t, m in pack["by_sample_type"].items():
                n = len(ids_by_type.get(t, set()))
                f.write(format_metrics_report(m, model_name, title_suffix=f" (Type={t}, n={n})"))
                f.write("\n")

    print(f"\n评估结果已保存到: {output_file}")

    json_output_file = os.path.join(args.output_dir, f"{model_name}_详细评估结果.json")
    with open(json_output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'model_name': model_name,
            'gold_file': args.gold,
            'pred_file': args.pred,
            'total_chars': total_chars,
            'gold_total_errors': gold_total_errors,
            'pred_total_errors': pred_total_errors,
            'sample_type_counts': {t: len(ids_by_type.get(t, set())) for t in ids_by_type.keys()},
            'results': results
        }, f, ensure_ascii=False, indent=2)

    print(f"详细结果(JSON)已保存到: {json_output_file}")


if __name__ == '__main__':
    main()