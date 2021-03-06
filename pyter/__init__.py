# -*- coding:utf-8 -*-
from __future__ import division, print_function
""" Copyright (c) 2011 Hiroyuki Tanaka. All rights reserved."""
import itertools as itrt
#from pyter import util # TODO
import util
from collections import namedtuple

align = namedtuple('align', 'd op')
word_wrap = namedtuple('word_wrap', 'w i')
# unwrap position indexed word
word_unwrap = lambda ww: ww.w if type(ww) is word_wrap else ww
word_index = lambda i, ww: ww.i if type(ww) is word_wrap else i
words_unwrap = lambda wwl: [ww.w for ww in wwl]

def ter(inputwords, refwords, align=False):
    """Calcurate Translation Error Rate
    inputwords and refwords are both list object.
    >>> ref = 'SAUDI ARABIA denied THIS WEEK information published in the AMERICAN new york times'.split()
    >>> hyp = 'THIS WEEK THE SAUDIS denied information published in the new york times'.split()
    >>> '{0:.3f}'.format(ter(hyp, ref))
    '0.308'
    """
    inputwords, refwords = list(inputwords), list(refwords)
    ed = CachedEditDistance(refwords)
    wrapped_words = [word_wrap(w, i) for i, w in enumerate(inputwords)]
    score_alignment = _ter(wrapped_words, refwords, ed)
    return score_alignment if align else score_alignment[0]


def _ter(iwords, rwords, mtd):
    """
    Translation Erorr Rate core function.
    returns a tuple: (score, alignment ['hyp-ref', 'hyp-ref', ...])
    """
    err = 0
    nced = NonCachedEditDistance(rwords)
    # print('[I]', u' '.join(iwords))
    # print('[R]', u' '.join(rwords))
    # print('[ED]', mtd(iwords))
    while True:
        delta, new_iwords = _shift(iwords, rwords, mtd)
        # print('[I]', u' '.join(iwords))
        # print('[R]', u' '.join(rwords))
        # print('[ED]', mtd(iwords))
        if delta <= 0:
            break
        err += 1
        iwords = new_iwords
    edit_dist = nced(iwords)
    return ((err + edit_dist[0]) / len(rwords), edit_dist[1])


def _shift(iwords, rwords, mtd):
    """ Shift the phrase pair most reduce the edit_distance
    Return True shift occurred, else False.
    """
    pre_score = mtd(words_unwrap(iwords))
    scores = []
    for isp, rsp, length in _findpairs(iwords, rwords):
        # cut out the shifted sequence [isp:isp+length]
        shifted_words = iwords[:isp] + iwords[isp + length:]
        # insert the sequence at its new home [rsp]
        shifted_words[rsp:rsp] = iwords[isp:isp + length]
        # score the newly shifted hypothesis h' in shifted_words
        score = mtd(words_unwrap(shifted_words))
        scores.append((pre_score - score, shifted_words))
    if not scores:
        return (0, iwords)
    scores.sort()
    return scores[-1]


def _findpairs(ws1, ws2):
    """
    Yield equal subsequences from two word sequences,
    starting at any two positions.

    yields the tuple of (ws1_start_point, ws2_start_point, length)
    So ws1[ws1_start_point:ws1_start_point+length] == ws2[ws2_start_point:ws2_start_point+length]
    """
    # unwrap position indexed word
    unw = word_unwrap
    for i1, i2 in itrt.product(range(len(ws1)), range(len(ws2))):
        if i1 == i2:
            continue  # take away if there is already in the same position
        if unw(ws1[i1]) == unw(ws2[i2]):
            # counting
            length = 1
            for j1, j2 in itrt.izip(range(i1 + 1, len(ws1)), range(i2 + 1, len(ws2))):
                if unw(ws1[j1]) == unw(ws2[j2]):
                    length += 1
                else:
                    break
            yield (i1, i2, length)


def _gen_matrix(col_size, row_size, default=None):
    return [[default for _ in range(row_size)] for __ in range(col_size)]


def edit_distance(s, t):
    """It's same as the Levenshtein distance"""
    l = _gen_matrix(len(s) + 1, len(t) + 1, None)
    # init first row
    l[0] = [align(x, 2) for x, _ in enumerate(l[0])]  # delete
    # init first col
    for x, y in enumerate(l):
        y[0] = align(x, 3)  # insert

    # unwrap position indexed word
    unw, wi = word_unwrap, word_index

    #
    # Minimum edit distance dynamic programming solution
    #
    # for morphing 't', we use the following operations... (note: something fishy, regarding above init ops. maybe 's'?)
    for i, j in itrt.product(range(1, len(s) + 1), range(1, len(t) + 1)):
        l[i][j] = min(align(d=l[i - 1][j].d + 1, op=3), # insert
                      align(d=l[i][j - 1].d + 1, op=2), # delete
                      align(d=l[i - 1][j - 1].d + (0 if unw(s[i - 1]) == unw(t[j - 1]) else 1), op=1)) # correct or substitute
    # NOTE: op number assignment *prefers the diagonal* (substitutions)
    # as we can only get alignments from there.

    #
    # Backtrack to obtain word alignment (now s-t. finally want hyp-ref)
    #
    alignment = []  # gets one entry for each position of 't'
    i = len(s)
    for j in range(len(t), 0, -1):
        op = l[i][j].op
        if op == 1: # ok or subs
            # note: we do not distinguish the two here.
            # this produces more alignments potentially at the price of precision.
            alignment[0:0] = ['%d-%d' % (wi(i-1, s[i-1]), wi(j-1, t[j-1]))]
        if op != 2: # delete: stay in same col
            i -= 1

    return (l[-1][-1].d, alignment)


class NonCachedEditDistance(object):
    def __init__(self, rwords):
        self.rwds = rwords

    def __call__(self, iwords):
        return edit_distance(iwords, self.rwds)

class CachedEditDistance(object):
    u""" 編集距離のキャッシュ版
    一回計算した途中結果を保存しておいて再利用する
    以前計算したリストをtrie木で保存して、重複する演算を省略する
    trieはネストした辞書で表現し、値に[次の辞書, キャッシュされた値]の長さ２のリストを用いる
    比較する対象はリスト化されている必要がある。
    """
    def __init__(self, rwords):
        self.rwds = rwords
        self._cache = {}
        self.list_for_copy = [0 for _ in range(len(self.rwds) + 1)]

    def __call__(self, iwords):
        start_position, cached_score = self._find_cache(iwords)
        score, newly_created_matrix = self._edit_distance(iwords, start_position, cached_score)
        self._add_cache(iwords, newly_created_matrix)  # もう一度たどって、キャッシュがないノードにキャッシュを挿入していく
        return score

    def _edit_distance(self, iwords, spos, cache):
        u""" sposが0の場合はキャッシュなし。
        """
        if cache is None:
            cache = [tuple(range(len(self.rwds) + 1))]
        else:
            cache = [cache] # 一つのrowにする
        l = cache + [list(self.list_for_copy) for _ in range(len(iwords) - spos)]
        # 先頭はキャッシュなので飛ばす。iwordsはsposから、lは1から計算
        assert len(l) - 1 == len(iwords) - spos
        for i, j in itrt.product(range(1, len(iwords) - spos + 1), range(len(self.rwds) + 1)):
            if j == 0:
                l[i][j] = l[i - 1][j] + 1
            else:
                l[i][j] = min(l[i - 1][j] + 1,
                              l[i][j - 1] + 1,
                              l[i - 1][j - 1] + (0 if iwords[spos + i - 1] == self.rwds[j - 1] else 1))
        return l[-1][-1], l[1:]

    def _add_cache(self, iwords, mat):
        node = self._cache
        skipnum = len(iwords) - len(mat)
        for i in range(skipnum):
            node = node[iwords[i]][0]
        assert len(iwords[skipnum:]) == len(mat)
        for word, row in itrt.izip(iwords[skipnum:], mat):
            if word not in node:
                node[word] = [{}, None]
            value = node[word]
            if value[1] is None:
                value[1] = tuple(row)
            node = value[0]  # nodeを一つ掘り下げる(drill down)

    def _find_cache(self, iwords):
        node = self._cache
        start_position, row = 0, None
        for idx, word in enumerate(iwords):
            if word in node:
                start_position = idx + 1
                node, row = node[word] # rowに値を入れておいて、
            else:
                break
        return start_position, row


def parse_args():
    import argparse             # new in Python 2.7!!
    parser = argparse.ArgumentParser(
        description='Translation Error Rate Evaluator',
        epilog="If you have an UnicodeEncodeError, try to set 'PYTHONIOENCODING' to your environment variables."
        )
    parser.add_argument('-r', '--ref', help='Reference file', required=True)
    parser.add_argument('-i', '--input', help='Input(test) file', required=True)
    parser.add_argument('-v', '--verbose', help='Show scores of each sentence.',
                        action='store_true', default=False)
    parser.add_argument('-l', '--lang', choices=['ja', 'en'], default='en', help='Language')
    parser.add_argument('-a', '--align', default=None, help='Produce hyp-ref word alignments')
    parser.add_argument('--force-token-mode', action='store_true', default=False, help='Use a space separated word as a unit')
    return parser.parse_args()


def main():
    import codecs
    import sys
    import itertools
    import math
    args = parse_args()
    ilines = [util.preprocess(x, args.lang) for x in codecs.open(args.input, 'r', 'utf-8').readlines()]
    rlines = [util.preprocess(x, args.lang) for x in codecs.open(args.ref, 'r', 'utf-8').readlines()]
    if len(ilines) != len(rlines):
        print("Error: input file has {0} lines, but reference has {1} lines.".format(len(ilines), len(rlines)))
        sys.exit(1)
    scores = []
    falign = open(args.align, 'w') if args.align is not None else None
    for lineno, (rline, iline) in enumerate(itertools.izip(ilines, rlines), start=1):
        if args.force_token_mode:
            rline, iline = rline.split(), iline.split()
        else:
            rline, iline = util.split(rline, args.lang), util.split(iline, args.lang)
        # iline, rline are list object
        score, alignment = ter(iline, rline, align=True)
        if args.align is not None:
            falign.write('%s\n' % ' '.join(alignment))
        scores.append(score)
        if args.verbose:
            print("Sentence {0}: {1:.4f}".format(lineno, score))
    if args.align is not None:
        falign.close()
    average = sum(scores) / len(scores)
    variance = sum((x - average) ** 2 for x in scores) / len(scores)
    stddev = math.sqrt(variance)
    print("Average={0:.4f}, Variance={1:.4f}, Standard Deviation={2:.4f}".format(average, variance, stddev))


if __name__ == '__main__':
    main()
