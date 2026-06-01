"""
Edit-pair normalization utilities for CLFEC.

Given an item id, the original input text, and a (snippet, corrected_snippet)
pair produced by a model, ``gen_cors`` returns a list of standardized
edit dictionaries that match the schema expected by ``eval.py``.

The standardization uses a CHERRANT-style annotator (Zhang et al., 2022) over
character-level Chinese tokenization to produce minimal-edit spans.
"""
import os
import sys

# Make local annotator package importable regardless of how the script is run
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from difflib import SequenceMatcher
from annotator import Tokenizer, Annotator
from annotator.classifier import Correction

# Initialize tokenizer and annotator (singletons; loaded once on import)
tokenizer = Tokenizer()
annotator = Annotator.create_default(strategy="multi_cheapest_strategy")

# 成对标点符号映射
pair_punctuations = {
    '“': '”',  # 中文双引号
    '‘': '’',  # 中文单引号
    "（": "）",  # 中文括号
    "【": "】",  # 中文方括号  
    "《": "》",  # 书名号
    "(": ")",   # 英文括号
    "[": "]",   # 英文方括号
    "{": "}",   # 英文花括号
    "「": "」",
    "〔": "〕",  # 六角括号
}


def best_match_with_constraints(text: str, sub_text: str, threshold: float = 0.9) -> tuple[int, int]:
    """
    获取最大相似度子串，要求子串至少长度为2
    找出 字符串 text 中与字符串 sub_text 最相似的子串，该子串必须满足：
    1.头字符和尾字符与 sub_text 相同；
    2.与 sub_text 的相似度是 所有满足条件的子串中最高的；
    3.相似度需要 超过某个指定阈值。

    Args:
        text: str, 文本
        sub_text: str, 子串
        threshold: float, 相似度阈值
    Returns:
        tuple[int, int]: 子串在文本中的位置。如果无匹配结果，则返回 (None, None)
    """
    if len(sub_text) < 2:
        return None, None

    best_score = 0.0
    best_start = -1
    best_end = -1

    len_a = len(text)
    b_start_char = sub_text[0]
    b_end_char = sub_text[-1]

    for i in range(len_a):
        if text[i] != b_start_char:
            continue
        for j in range(i + 1, len_a):
            if text[j] != b_end_char:
                continue
            candidate = text[i:j + 1]
            # 如果候选子串长度与sub_text长度相差超过5，则不考虑
            if abs(len(candidate) - len(sub_text)) > 5:
                continue
            score = SequenceMatcher(None, candidate, sub_text).ratio()
            if score > best_score:
                best_score = score
                best_start = i
                best_end = j + 1

    if best_score >= threshold:
        return best_start, best_end
    else:
        return None, None


def find_sub_text_position(text: str, sub_text: str) -> tuple[int, int]:
    """
    寻找sub_text在text中的位置。如果不在text中，则尝试从text中寻找最相似的子串。
    Args:
        text: str, 文本
        sub_text: str, 子串
    Returns:
        tuple[int, int]: 子串在文本中的位置。如果无匹配结果，则返回 (None, None)
    """
    if len(sub_text) == 0:
        return None, None
    # 如果sub_text在text中，则直接返回其位置
    if sub_text in text:
        start = text.find(sub_text)
        end = start + len(sub_text)
        return start, end
    # 如果sub_text不在text中，则尝试从text中寻找最相似的子串
    else:
        return best_match_with_constraints(text, sub_text)


def merge_cors(cors, src_tokens):
    """
    处理特殊情况
    1、成对标点符号的修改需要合并
    """
    if not cors:
        return cors
    
    # 获取所有成对标点符号
    all_pair_chars = set(pair_punctuations.keys()) | set(pair_punctuations.values())
    # 按起始位置排序
    sorted_cors = sorted(cors, key=lambda cor: cor.inds[0])

    # 检查是否有涉及成对标点符号的修改
    has_pair_punct_changes = []
    for i, cor in enumerate(sorted_cors):
        error_word = "".join([token[0] for token in src_tokens[cor.inds[0]:cor.inds[1]]])
        toks = cor.toks.replace(" ", "")
        if toks == "-NONE-":
            candidate_word = ""
        else:
            candidate_word = toks
        # 检查修改中是否涉及成对标点符号
        if any(char in all_pair_chars for char in candidate_word) or any(char in all_pair_chars for char in error_word):
            has_pair_punct_changes.append(i)
    
    # 如果没有涉及成对标点符号的修改，直接返回
    if not has_pair_punct_changes:
        return cors
    
    # 检查是否存在成对的标点符号修改
    merge_ranges = []
    
    # 寻找成对标点符号的配对
    for i in range(len(has_pair_punct_changes)):
        for j in range(i + 1, len(has_pair_punct_changes)):
            idx1, idx2 = has_pair_punct_changes[i], has_pair_punct_changes[j]
            toks1 = sorted_cors[idx1].toks.replace(" ", "")
            toks2 = sorted_cors[idx2].toks.replace(" ", "")
            candidate1 = toks1 if toks1 != "-NONE-" else ""
            candidate2 = toks2 if toks2 != "-NONE-" else ""
            # 检查是否存在成对关系
            found_pair = False
            for char1 in candidate1:
                if char1 in pair_punctuations:
                    end_punct = pair_punctuations[char1]
                    if end_punct in candidate2:
                        found_pair = True
                        break
            # 如果两个修改相邻，则可以合并。否则中间也存在修改，不做合并
            if found_pair and abs(idx1 - idx2) == 1:
                merge_ranges.append((idx1, idx2))
    
    # 如果没有找到需要合并的配对，返回原始cors
    if not merge_ranges:
        return cors
    
    # 执行合并
    merged_cors = []
    processed_indices = set()
    
    for start_idx, end_idx in merge_ranges:
        if start_idx in processed_indices or end_idx in processed_indices:
            continue
        
        # 合并从start_idx到end_idx之间的所有修改
        merge_start = sorted_cors[start_idx].inds[0]
        merge_end = sorted_cors[end_idx].inds[1]

        toks_start = sorted_cors[start_idx].toks.replace(" ", "")
        toks_end = sorted_cors[end_idx].toks.replace(" ", "")
        candidate_start = toks_start if toks_start != "-NONE-" else ""
        candidate_end = toks_end if toks_end != "-NONE-" else ""
        
        # 标记这些索引为已处理（包括中间的所有修改）
        for idx in range(start_idx, end_idx + 1):
            processed_indices.add(idx)
        
        # 构建修改后的文本，并且确定错误类型
        corrected_text = candidate_start + "".join([token[0] for token in src_tokens[sorted_cors[start_idx].inds[1]: sorted_cors[end_idx].inds[0]]]) + candidate_end
        merged_cors.append(Correction("R", corrected_text, (merge_start, merge_end)))
    
    # 添加未被合并的修改
    for i, cor in enumerate(sorted_cors):
        if i not in processed_indices:
            merged_cors.append(cor)
    
    # 按起始位置重新排序
    merged_cors.sort(key=lambda x: x.inds[0])
    
    return merged_cors


def merge_missing(cors):
    """
    处理missing类型，如果missing位置后面一个cor对当前标记的插入位置有修改，此时不能直接用inds[0]位置向左扩展，直接合并为一个cor
    """
    if not cors:
        return cors
    
    for i, cor in enumerate(cors):
        if cor.op == "M" and i < len(cors) - 1:
            if cors[i + 1].inds[0] <= cor.inds[0] <= cors[i + 1].inds[1]:
                # 合并为S类型
                cors[i] = Correction("S", cor.toks + cors[i + 1].toks, (cor.inds[0], cors[i + 1].inds[1]))
                cors.pop(i + 1)
    return cors


def yield_errant_correction(item_id: str, sentence: str, corrected: str):
    """
    使用errant库生成纠错结果，并返回纠错结果列表
    Args:
        item_id: 条目ID
        sentence: 原始句子
        corrected: 纠正后的句子
    Returns:
        correction_lst: 纠错结果列表
    """
    # 如果原始句子或纠正后的句子为空，或两者相同，则直接返回空列表
    if not sentence or not corrected or sentence == corrected:
        return []
    src_tokens, tgt_tokens = tokenizer([sentence, corrected])
    annotator_result = annotator(src_tokens, tgt_tokens)
    # 先做特殊情况处理，合并成对标点
    merged_annotator_result = merge_cors(annotator_result, src_tokens)
    # 处理missing类型，如果missing位置后面一个cor对当前标记的插入位置有修改，此时不能直接用inds[0]位置向左扩展，直接合并为一个cor
    merged_annotator_result = merge_missing(merged_annotator_result)
    correction_lst = []
    for cor in merged_annotator_result:
        if cor.op in ["S", "R", "W"]:
            toks = cor.toks.replace(" ", "")
            # 遇到需要做删除的情况，错词和建议词需要扩展，默认向左扩展一词，当位置为开头时，向右扩展一词
            if toks == "-NONE-":
                token_start, token_end = cor.inds[0], cor.inds[1]
                error_word = "".join([token[0] for token in src_tokens[token_start:token_end]])
                # 如果要删除的词是空格，或标点冗余，那么不需要扩展(考虑多个空格的情况)
                if error_word.strip() == "":
                    start = src_tokens[token_start][1]
                    end = start + len(error_word)
                    candidate_word = ""
                elif token_start == 0:
                    error_word = "".join([token[0] for token in src_tokens[token_start:token_end + 1]])
                    start = src_tokens[token_start][1]
                    end = start + len(error_word)
                    candidate_word = src_tokens[token_end][0]
                else:
                    error_word = "".join([token[0] for token in src_tokens[token_start - 1:token_end]])
                    start = src_tokens[token_start - 1][1]
                    end = start + len(error_word)
                    candidate_word = src_tokens[token_start - 1][0]
            else:
                token_start, token_end = cor.inds[0], cor.inds[1]
                error_word = "".join([token[0] for token in src_tokens[token_start:token_end]])
                start = src_tokens[token_start][1]
                end = start + len(error_word)
                candidate_word = toks
        else:  # Missing
            if cor.inds[0] != len(src_tokens):
                token_start, token_end = cor.inds[0], cor.inds[1] + 1
                error_word = "".join([token[0] for token in src_tokens[token_start:token_end]])
                start = src_tokens[token_start][1]
                end = start + len(error_word)
                if cor.toks.strip() == "":
                    candidate_word = cor.toks + error_word
                else:
                    candidate_word = cor.toks.replace(" ", "") + error_word
            else:
                token_start, token_end = cor.inds[0] - 1, cor.inds[1]
                error_word = "".join([token[0] for token in src_tokens[token_start:token_end]])
                start = src_tokens[token_start][1]
                end = start + len(error_word)
                if cor.toks.strip() == "":
                    candidate_word = error_word + cor.toks
                else:
                    candidate_word = error_word + cor.toks.replace(" ", "")
        correction_lst.append((start, end, error_word, candidate_word, item_id))
    return correction_lst


def gen_cors(item_id: str, input_text: str, original: str, corrected: str):
    """
    生成纠错结果
    
    Args:
        item_id: 条目ID
        input_text: 输入文本
        original: 原始句子
        corrected: 纠正后的句子
    
    Returns:
        纠错结果列表
    """
    new_cors = []
    llm_output_sentence = original.rstrip()
    llm_output_corrected = corrected.rstrip()
    sentence_start, sentence_end = find_sub_text_position(input_text, llm_output_sentence)
    if sentence_start is None:
        return []
    sentence_in_doc = input_text[sentence_start:sentence_end]
    cors = yield_errant_correction(item_id, sentence_in_doc, llm_output_corrected)
    for inner_start, inner_end, error_word, candidate_word, item_id in cors:
        new_cors.append({
            "start": sentence_start + inner_start,
            "end": sentence_start + inner_end,
            "error_word": error_word,
            "candidate_word": candidate_word,
            "item_id": item_id
        })
    return new_cors


def extract_from_custom_model(text, module_name=None):
    """
    自研模型结果格式为 aaa⇒bbb⧉ccc⇒ddd⧉...
    Returns:
        list: 解析后的列表 [["aaa", "bbb"], ["ccc", "ddd"], ...]
    """
    if not text:
        return None
    # 正常结果不会以⇒或⧉开头或结尾，如果text以⇒或⧉开头或结尾，则去掉
    if text.startswith("⇒") or text.startswith("⧉"):
        text = text[1:]
    if text.endswith("⇒") or text.endswith("⧉"):
        text = text[:-1]
    if "⇒" not in text:
        return None
    result = []
    has_error = False
    for correcttion in text.split("⧉"):
        ans = correcttion.split("⇒")
        if len(ans) == 2:
            result.append(ans)
        else:
            has_error = True
    return result


if __name__ == "__main__":
    id = "test"
    input_text = "2.2.2水体环境质量评价因子检测系统\n先对模糊综合评价方法进行介绍，模糊综合评价是一种基于模糊集合理论的综合评价方法，主要解决评价过程中存在的不确定性和模糊性问题。"
    original = "2.2.2水体环境质量评价因子检测系统"
    corrected = "2.2.2 水体环境质量评价因子检测系统"
    print(gen_cors(id, input_text, original, corrected))