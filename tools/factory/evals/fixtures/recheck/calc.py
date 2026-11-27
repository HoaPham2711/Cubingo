"""Fixture eval (vòng kiểm lại): clamp đã sửa đúng; fmt có lỗi nhỏ có sẵn, ngoài phạm vi vòng sửa."""


def clamp(x, lo, hi):
    return max(lo, min(x, hi))


def fmt(x):
    # Có sẵn từ trước, không thuộc diff sửa: -0.0 in ra "-0.0" (thẩm mỹ, không ai gọi với -0.0).
    return f"{x:.1f}"
