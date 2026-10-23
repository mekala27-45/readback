"""Wilson intervals, the two proportion comparison, Benjamini-Hochberg and Cohen's kappa."""

from __future__ import annotations

import math
from collections.abc import Sequence

Z95 = 1.959963984540054


def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def difference_interval(a: int, na: int, b: int, nb: int, z: float = Z95) -> tuple[float, float, float]:
    """The difference of two proportions with Newcombe's hybrid Wilson interval, and a two sided p."""
    pa, pb = (a / na if na else 0.0), (b / nb if nb else 0.0)
    la, ua = wilson(a, na, z)
    lb, ub = wilson(b, nb, z)
    d = pa - pb
    low = d - math.sqrt((pa - la) ** 2 + (ub - pb) ** 2)
    high = d + math.sqrt((ua - pa) ** 2 + (pb - lb) ** 2)
    pooled = (a + b) / (na + nb) if na + nb else 0.0
    se = math.sqrt(pooled * (1 - pooled) * (1 / na + 1 / nb)) if na and nb and 0 < pooled < 1 else 0.0
    p = 1.0 if se == 0 else math.erfc(abs(d) / se / math.sqrt(2))
    return low, high, p


def benjamini_hochberg(pvalues: Sequence[float], q: float = 0.05) -> list[bool]:
    """Which hypotheses are rejected at false discovery rate q, in input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    cutoff = -1
    for rank, i in enumerate(order, start=1):
        if pvalues[i] <= q * rank / m:
            cutoff = rank
    rejected = [False] * m
    for rank, i in enumerate(order, start=1):
        if rank <= cutoff:
            rejected[i] = True
    return rejected


def kappa(a: Sequence[bool], b: Sequence[bool]) -> float | None:
    """Cohen's kappa for two pass or fail raters over the same items."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    agree = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return None if expected == 1 else (agree - expected) / (1 - expected)


def median(values: Sequence[float]) -> float | None:
    s = sorted(values)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(values: Sequence[float], p: float) -> float | None:
    s = sorted(values)
    if not s:
        return None
    return s[min(len(s) - 1, max(0, round(p * (len(s) - 1))))]
