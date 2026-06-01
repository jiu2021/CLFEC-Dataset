import functools
from typing import List
from pypinyin import pinyin, Style, lazy_pinyin
import jieba


class Tokenizer:
    """
    分词器
    """
    def __init__(self):
        self.jieba_tokenizer = jieba.Tokenizer()
        self.jieba_tokenizer.initialize()
        self.tokenizer = functools.partial(self.split_word)

    def __call__(self,
                 input_strings: List[str]
                 ) -> List:
        """
        分词函数
        :param input_strings: 需要分词的字符串列表
        :return: 分词后的结果列表，由元组组成，元组为(token,pos_tag,pinyin)的形式
        """
        results = self.tokenizer(input_strings)
        return results

    def segment(self, input_string: str) -> List:
        words = []
        positions = []
        pinyins = []
        for word, pos, _ in self.jieba_tokenizer.tokenize(input_string, HMM=False):
            words.append(word)
            positions.append(pos)
            pinyins.append(lazy_pinyin(word))
        return words, positions, pinyins
    
    @staticmethod
    def split_char(input_strings: List[str]) -> List:
        """
        分字函数
        :param input_strings: 需要分字的字符串
        :return: 分字结果
        """
        results = []
        for input_string in input_strings:
            segment_string = [char for char in input_string]
            results.append([(char, "unk", pinyin(char, style=Style.NORMAL, heteronym=True)[0]) for char in segment_string])
        return results
    
    def split_word(self, input_strings: List[str]) -> List:
        """
        分词函数
        :param input_strings: 需要分词的字符串
        :return: 分词结果
        """
        result = []
        for input_string in input_strings:
            s, p , pinyin = self.segment(input_string)
            result.append(list(zip(s, p, pinyin)))
        return result
