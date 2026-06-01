from collections import namedtuple

Correction = namedtuple(
    "Correction",
    [
        "op",
        "toks",
        "inds",
    ],
)


class Classifier:
    """
    错误类型分类器
    """
    @staticmethod
    def get_pos_type(pos):
        if pos in {"n", "nd"}:
            return "NOUN"
        if pos in {"nh", "ni", "nl", "ns", "nt", "nz"}:
            return "NOUN-NE"
        if pos in {"v"}:
            return "VERB"
        if pos in {"a", "b"}:
            return "ADJ"
        if pos in {"c"}:
            return "CONJ"
        if pos in {"r"}:
            return "PRON"
        if pos in {"d"}:
            return "ADV"
        if pos in {"u"}:
            return "AUX"
        # if pos in {"k"}:  # TODO 后缀词比例太少，暂且分入其它
        #     return "SUFFIX"
        if pos in {"m"}:
            return "NUM"
        if pos in {"p"}:
            return "PREP"
        if pos in {"q"}:
            return "QUAN"
        if pos in {"wp"}:
            return "PUNCT"
        return "OTHER"

    def __call__(self,
                 src,
                 tgt,
                 edits,
                 verbose: bool = False):
        """
        为编辑操作划分错误类型
        :param src: 错误句子信息
        :param tgt: 正确句子信息
        :param edits: 编辑操作
        :param verbose: 是否打印信息
        :return: 划分完错误类型后的编辑操作
        """
        results = []
        src_tokens = [x[0] for x in src]
        tgt_tokens = [x[0] for x in tgt]
        for edit in edits:
            error_type = edit[0]
            src_span = " ".join(src_tokens[edit[1]: edit[2]])
            tgt_span = " ".join(tgt_tokens[edit[3]: edit[4]])
            # print(tgt_span)
            cor = None
            if error_type[0] == "T":
                cor = Correction("W", tgt_span, (edit[1], edit[2]))
            elif error_type[0] == "D":
                # 字级别可以只需要根据操作划分类型即可
                cor = Correction("R", "-NONE-", (edit[1], edit[2]))
            elif error_type[0] == "I":
                # 字级别可以只需要根据操作划分类型即可
                cor = Correction("M", tgt_span, (edit[1], edit[2]))
            elif error_type[0] == "S":
                # 字级别可以只需要根据操作划分类型即可
                cor = Correction("S", tgt_span, (edit[1], edit[2]))
            results.append(cor)
        if verbose:
            print("========== Corrections ==========")
            for cor in results:
                print("Type: {:s}, Position: {:d} -> {:d}, Target: {:s}".format(cor.op, cor.inds[0], cor.inds[1], cor.toks))
        return results
