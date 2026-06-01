#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time : 3/6/2024 下午4:42
# @Author : zhangzidong
# @Email: zhangzidong@wps.cn
import os
import numpy as np
from string import punctuation
from typing import List, Tuple, Dict


chinese_punct = "！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､、〃》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—‘'‛“”„‟…‧﹏"
english_punct = punctuation
punct = chinese_punct + english_punct


def check_all_chinese(word):
    """
    判断一个单词是否全部由中文组成
    :param word:
    :return:
    """
    return all(['\u4e00' <= ch <= '\u9fff' for ch in word])


class Alignment:
    """
    对齐错误句子和正确句子，
    使用编辑距离算法抽取编辑操作
    """

    def __init__(
            self
    ) -> None:
        self.insertion_cost = 1
        self.deletion_cost = 1
        self.substitution_cost = 1
        # Because we use character level tokenization, this doesn't currently use POS
        self.align_seqs = []

    def __call__(self,
                 src: List[Tuple],
                 tgt: List[Tuple],
                 verbose: bool = False):
        cost_matrix, oper_matrix = self.align(src, tgt)
        align_seq = self.get_cheapest_align_seq(oper_matrix)

        if verbose:
            print("========== Seg. and POS: ==========")
            print(src)
            print(tgt)
            print("========== Cost Matrix ==========")
            print(cost_matrix)
            print("========== Oper Matrix ==========")
            print(oper_matrix)
            print("========== Alignment ==========")
            print(align_seq)
            print("========== Results ==========")
            for a in align_seq:
                print(a[0], src[a[1]: a[2]], tgt[a[3]: a[4]])
        return align_seq

    def align(self,
              src: List[Tuple],
              tgt: List[Tuple]):
        """
        Based on ERRANT's alignment
        基于改进的动态规划算法，为原句子的每个字打上编辑标签，以便使它能够成功转换为目标句子。
        编辑操作类别：
        1) M：Match，即KEEP，即当前字保持不变
        2) D：Delete，删除，即当前字需要被删除
        3) I：Insert，插入，即当前字需要被插入
        4) T：Transposition，移位操作，即涉及到词序问题
        """
        cost_matrix = np.zeros((len(src) + 1, len(tgt) + 1))  # 编辑cost矩阵
        oper_matrix = np.full(
            (len(src) + 1, len(tgt) + 1), "O", dtype=object
        )  # 操作矩阵
        # Fill in the edges
        for i in range(1, len(src) + 1):
            cost_matrix[i][0] = cost_matrix[i - 1][0] + 1
            oper_matrix[i][0] = ["D"]
        for j in range(1, len(tgt) + 1):
            cost_matrix[0][j] = cost_matrix[0][j - 1] + 1
            oper_matrix[0][j] = ["I"]

        # Loop through the cost matrix
        for i in range(len(src)):
            for j in range(len(tgt)):
                # Matches
                if src[i][0] == tgt[j][0]:  # 如果两个字相等，则匹配成功（Match），编辑距离为0
                    cost_matrix[i + 1][j + 1] = cost_matrix[i][j]
                    oper_matrix[i + 1][j + 1] = ["M"]
                # Non-matches
                else:
                    del_cost = cost_matrix[i][j + 1] + self.deletion_cost  # 由删除动作得到的总cost
                    ins_cost = cost_matrix[i + 1][j] + self.insertion_cost  # 由插入动作得到的总cost
                    sub_cost = cost_matrix[i][j] + self.substitution_cost  # 由替换动作得到的总cost
                    # Calculate transposition cost
                    # 计算移位操作的总cost
                    trans_cost = float("inf")
                    k = 1
                    while (
                            i - k >= 0
                            and j - k >= 0
                            and cost_matrix[i - k + 1][j - k + 1]
                            != cost_matrix[i - k][j - k]
                    ):
                        p1 = sorted([a[0] for a in src][i - k: i + 1])
                        p2 = sorted([b[0] for b in tgt][j - k: j + 1])
                        if p1 == p2:
                            trans_cost = cost_matrix[i - k][j - k] + k
                            break
                        k += 1

                    costs = [trans_cost, sub_cost, ins_cost, del_cost]
                    ind = costs.index(min(costs))
                    cost_matrix[i + 1][j + 1] = costs[ind]
                    # 根据最小代价的操作类型直接更新操作矩阵
                    if ind == 0:
                        # Transposition 操作
                        if oper_matrix[i + 1][j + 1] == "O":
                            oper_matrix[i + 1][j + 1] = ["T" + str(k + 1)]
                        else:
                            oper_matrix[i + 1][j + 1].append("T" + str(k + 1))
                    elif ind == 1:
                        # Substitute 操作
                        if oper_matrix[i + 1][j + 1] == "O":
                            oper_matrix[i + 1][j + 1] = ["S"]
                        else:
                            oper_matrix[i + 1][j + 1].append("S")
                    elif ind == 2:
                        # Insert 操作
                        if oper_matrix[i + 1][j + 1] == "O":
                            oper_matrix[i + 1][j + 1] = ["I"]
                        else:
                            oper_matrix[i + 1][j + 1].append("I")
                    else:
                        # Delete 操作
                        if oper_matrix[i + 1][j + 1] == "O":
                            oper_matrix[i + 1][j + 1] = ["D"]
                        else:
                            oper_matrix[i + 1][j + 1].append("D")
        return cost_matrix, oper_matrix

    def _dfs(self, i, j, align_seq_now, oper_matrix, strategy="all"):
        """
        深度优先遍历，获取最小编辑距离相同的所有序列
        """
        if i + j == 0:
            self.align_seqs.append(align_seq_now)
        else:
            ops = oper_matrix[i][j]  # 可以类比成搜索一棵树从根结点到叶子结点的所有路径
            if strategy != "all": ops = ops[:1]
            for op in ops:
                if op in {"M", "S"}:
                    self._dfs(i - 1, j - 1, align_seq_now + [(op, i - 1, i, j - 1, j)], oper_matrix, strategy)
                elif op == "D":
                    self._dfs(i - 1, j, align_seq_now + [(op, i - 1, i, j, j)], oper_matrix, strategy)
                elif op == "I":
                    self._dfs(i, j - 1, align_seq_now + [(op, i, i, j - 1, j)], oper_matrix, strategy)
                else:
                    k = int(op[1:])
                    self._dfs(i - k, j - k, align_seq_now + [(op, i - k, i, j - k, j)], oper_matrix, strategy)

    def get_cheapest_align_seq(self, oper_matrix):
        """
        回溯获得编辑距离最小的编辑序列
        """
        self.align_seqs = []
        i = oper_matrix.shape[0] - 1
        j = oper_matrix.shape[1] - 1
        if abs(i - j) > 10:
            self._dfs(i, j, [], oper_matrix, "first")
        else:
            self._dfs(i, j, [], oper_matrix, "all")
        final_align_seqs = [seq[::-1] for seq in self.align_seqs]
        return final_align_seqs
