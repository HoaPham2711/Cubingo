"""Fixture eval: kẹp số vào [lo, hi]. CÓ LỖI CÀI SẴN: bỏ qua hi."""


def clamp(x, lo, hi):
    return max(lo, x)
