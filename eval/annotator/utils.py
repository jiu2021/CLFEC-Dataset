# coding=utf-8
"""
@author: zhangzidong
@contact: zhangzidong@wps.cn
@file: utils.py
@date: 2024/8/8 上午11:04
@desc: 
"""
import string
from core import Sentence
from core.algo.utils import is_chinese_char


chinese_punct = "！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､、〃》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—‘'‛“”„‟…‧﹏"


def check_symbol(sentence: str):
    """
    判断一个句子是否全部为符号
    Args:
        sentence:

    Returns: True or False
    """
    symbols = chinese_punct + string.punctuation + string.whitespace + "\u3000"
    # 检查句子中的每个字符是否都是符号
    for char in sentence:
        if char not in symbols:
            return False
    return True


def check_chinese(sentence: str):
    """
    判断一个句子是否大多数为中文
    Args:
        sentence:

    Returns: True or False
    """
    zh_count = 0
    for char in sentence:
        if is_chinese_char(char):
            zh_count += 1
    # 如果句子中的中文过少，则无需计算比例
    if zh_count <= 5:
        return False
    return True if zh_count/len(sentence) >= 0.7 else False


def filter_sent(sent_list: [Sentence]):
    res = []
    for sent_obj in sent_list:
        if check_symbol(sent_obj.sent):
            continue
        if not check_chinese(sent_obj.sent):
            continue
        res.append(sent_obj)
    return res


def check_word(start, error_word, word_lst):
    """
    检查error_word在word_lst中的位置，如果在，则返回该位置，否则返回-1
    """
    if error_word in word_lst:
        if start == 0 and error_word == word_lst[0]:
            return 0
        index = 0
        for i, word in enumerate(word_lst):
            if index >= start:
                break
            index += len(word)
        if index == start and error_word == word:
            return i
        else:
            return -1
    else:
        return -1


def expand_result(text, word_lst, start, end):
    """
    扩大修正范围，判断error_word是否在分词结果中，如果在，则以词为单位扩大修正范围；否则以字为单位扩大修正范围
    """
    error_word = text[start:end]
    # 首先判断error_word是否在分词结果中
    index = check_word(start, error_word, word_lst)
    if index != -1:
        if index == 0:
            end = end + len(word_lst[1])
            error_word = error_word + word_lst[1]
            candidate_word = word_lst[1]
            return start, end, error_word, candidate_word
        else:
            start = start - len(word_lst[index-1])
            error_word = word_lst[index-1] + error_word
            candidate_word = word_lst[index-1]
            return start, end, error_word, candidate_word
    else:
        if start == 0:
            end = end + 1
            error_word = text[start:end]
            candidate_word = text[end-1]
        else:
            start = start - 1
            error_word = text[start:end]
            candidate_word = text[start]
        return start, end, error_word, candidate_word