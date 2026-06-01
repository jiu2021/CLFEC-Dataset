from typing import List, Tuple
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .alignment import Alignment
from .merger import Merger
from .classifier import Classifier


class Annotator:
    def __init__(self,
                 align: Alignment,
                 merger: Merger,
                 classifier: Classifier,
                 strategy: str = "first"):
        self.align = align
        self.merger = merger
        self.classifier = classifier
        self.strategy = strategy

    @classmethod
    def create_default(cls, strategy: str = "first"):
        """
        Default parameters used in the paper
        """
        align = Alignment()
        merger = Merger()
        classifier = Classifier()
        return cls(align, merger, classifier, strategy)

    def __call__(self,
                 src: List[Tuple],
                 tgt: List[Tuple],
                 verbose: bool = False):
        """
        Align sentences and annotate them with error type information
        """
        cors = []
        align_objs = self.align(src, tgt)
        edit_objs = []
        align_idx = 0
        if self.strategy == "first":
            align_objs = align_objs[:1]
        for align_obj in align_objs:
            edits = self.merger(align_obj, src, tgt, verbose)
            if edits not in edit_objs:
                edit_objs.append(edits)
                align_idx += 1
                cors = self.classifier(src, tgt, edits, verbose)
        return cors
