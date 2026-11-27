"""Fixture eval: kẹp số vào [lo, hi] — bản đúng."""


def clamp(x, lo, hi):
    return max(lo, min(x, hi))
