"""Fixture eval (quét cạn): bộ sửa có xem trước. Bất biến: mọi method public đổi state phải gọi
self._bake() TRƯỚC, để phép xoay đang xem trước được áp vào `committed` trước thao tác mới."""


class Editor:
    def __init__(self):
        self.committed = []   # thao tác đã áp
        self.preview = None   # phép xoay đang xem trước, chưa áp
        self.tab = "rotate"

    def _bake(self):
        if self.preview is not None:
            self.committed.append(("rotate", self.preview))
            self.preview = None

    def rotate_preview(self, deg):
        self.preview = deg

    def crop(self, box):
        self._bake()
        self.committed.append(("crop", box))

    def undo(self):
        if self.committed:
            self.committed.pop()

    def select_tab(self, name):
        self.tab = name

    def save(self):
        return list(self.committed)
