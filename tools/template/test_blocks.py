"""Test cho tools/template/blocks.py — cắt khối đánh dấu `<họ>:begin … <họ>:end` (Swift / Markdown / hash).

Chạy: python3 -m unittest discover -s tools/template -p 'test_*.py'
Chỉ chuỗi trong bộ nhớ — không đọc/ghi file nào (chạy được ở app sinh ra).
"""
import sys
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocks  # noqa: E402


def d(s):
    return textwrap.dedent(s).lstrip("\n")


class BlocksTests(unittest.TestCase):
    def test_style_for(self):
        self.assertEqual(blocks.style_for("AppHost/AppHost/A.swift"), "swift")
        self.assertEqual(blocks.style_for("CLAUDE.md"), "md")
        for rel in ("AppHost/project.yml", "x.yaml", "app.config.toml", "tools/a.sh"):
            self.assertEqual(blocks.style_for(rel), "hash", rel)
        self.assertIsNone(blocks.style_for("AppHost/Info.plist"))
        self.assertIsNone(blocks.style_for("README"))
        self.assertEqual(set(blocks.STYLES), {"swift", "hash", "md"})

    def test_cat_khoi_markdown(self):
        text = d("""
            # App

            Đoạn chung.

            <!-- sample:begin -->
            ## Tính năng mẫu

            Tả mẫu.
            <!-- sample:end -->

            ## Build
            """)
        self.assertEqual(blocks.cut(text, "sample", "md"), "# App\n\nĐoạn chung.\n\n## Build\n")
        # Khối ở cuối file: không để dòng trống thừa ở cuối.
        text = "# App\n\nĐoạn.\n\n<!-- sample:begin -->\nTả mẫu.\n<!-- sample:end -->\n"
        self.assertEqual(blocks.cut(text, "sample", "md"), "# App\n\nĐoạn.\n")
        # Khối giữa hai dòng của một đoạn: hai dòng nối liền.
        text = "a\n  <!-- sample:begin -->\nb\n<!-- sample:end -->  \nc\n"
        self.assertEqual(blocks.cut(text, "sample", "md"), "a\nc\n")
        self.assertEqual(blocks.scan(text, "sample", "md"), [(2, "begin"), (4, "end")])
        # Markdown không có nhánh else.
        with self.assertRaises(blocks.BlockError) as cm:
            blocks.cut("<!-- sample:else-begin -->\nx\n<!-- sample:else-end -->\n", "sample", "md")
        self.assertEqual(cm.exception.line, 1)

    def test_cat_khoi_hash_va_bo_comment_nhanh_else(self):
        text = d("""
            targets:
              App:
                sources:
                  # sample:begin
                  - path: Sample
                  # sample:end
                  # sample:else-begin
                  # - path: Other
                  #
                  # sample:else-end
                  - path: App
            """)
        self.assertEqual(blocks.cut(text, "sample", "hash"),
                         "targets:\n  App:\n    sources:\n      - path: Other\n\n      - path: App\n")
        self.assertEqual(blocks.scan(text, "sample", "hash"),
                         [(4, "begin"), (6, "end"), (7, "else-begin"), (10, "else-end")])
        with self.assertRaises(blocks.BlockError) as cm:
            blocks.cut("# sample:else-begin\n- path: X\n# sample:else-end\n", "sample", "hash")
        self.assertEqual(cm.exception.line, 2)

    def test_dau_khong_cap_nem_loi_co_so_dong(self):
        for text, style, line in (
            ("a\n<!-- template:begin -->\nb\n", "md", 2),
            ("a\nb\n<!-- template:end -->\n", "md", 3),
            ("x\n# sample:begin\n", "hash", 2),
            ("let a = 1\n// sample:end\n", "swift", 2),
            ("a <!-- sample:begin -->\nb\n<!-- sample:end -->\n", "md", 1),   # dấu dính chữ
            ("  # sample:begin trailing\n# sample:end\n", "hash", 1),
        ):
            fam = "template" if "template:" in text else "sample"
            with self.subTest(text=text):
                with self.assertRaises(blocks.BlockError) as cm:
                    blocks.scan(text, fam, style)
                self.assertEqual(cm.exception.line, line)
                with self.assertRaises(blocks.BlockError):
                    blocks.cut(text, fam, style)

    def test_khoi_long_nhau_bi_tu_choi(self):
        text = "<!-- sample:begin -->\n<!-- sample:begin -->\nx\n<!-- sample:end -->\n<!-- sample:end -->\n"
        with self.assertRaises(blocks.BlockError) as cm:
            blocks.scan(text, "sample", "md")
        self.assertEqual(cm.exception.line, 2)
        self.assertIn("lồng", str(cm.exception))
        text = "// sample:else-begin\n// sample:begin\n// sample:end\n// sample:else-end\n"
        with self.assertRaises(blocks.BlockError) as cm:
            blocks.cut(text, "sample", "swift")
        self.assertEqual(cm.exception.line, 2)

    def test_ho_khac_khong_bi_dung(self):
        text = d("""
            Đầu.
            <!-- template:begin -->
            Chỉ template.
            <!-- template:end -->
            <!-- sample:begin -->
            Mẫu.
            <!-- sample:end -->
            Cuối.
            """)
        self.assertEqual(blocks.cut(text, "sample", "md"),
                         "Đầu.\n<!-- template:begin -->\nChỉ template.\n<!-- template:end -->\nCuối.\n")
        self.assertEqual(blocks.cut(text, "template", "md"),
                         "Đầu.\n<!-- sample:begin -->\nMẫu.\n<!-- sample:end -->\nCuối.\n")
        self.assertEqual(blocks.scan(text, "template", "md"), [(2, "begin"), (4, "end")])
        # Nhắc dấu trong chữ (backtick, giữa dòng) không phải dấu và không lỗi ở Markdown.
        prose = "Phần mẫu nằm giữa `<!-- sample:begin -->` và `<!-- sample:end -->`.\nKhối `// sample:begin`.\n"
        self.assertEqual(blocks.cut(prose, "sample", "md"), prose)
        self.assertEqual(blocks.scan(prose, "sample", "md"), [])
        # Trong khối code rào (```), dòng trông như dấu chỉ là ví dụ — không cắt, không lỗi.
        fenced = "Ví dụ:\n\n```markdown\n<!-- sample:begin -->\nphần mẫu\n<!-- sample:end -->\n```\n"
        self.assertEqual(blocks.cut(fenced, "sample", "md"), fenced)
        self.assertEqual(blocks.scan("```\n<!-- sample:begin -->\n```\n", "sample", "md"), [])

    def test_swift_giu_hanh_vi_cu(self):
        text = d("""
            struct Shell {
                let a = 1

                // sample:begin
                let store = SampleItemStore()
                // sample:end

                let b = 2
                // sample:begin
                let c = SampleC()
                // sample:end
            }
            """)
        # Không hai dòng trống liền nhau, không dòng trống ngay trước `}` (hành vi của remove_sample trước P4).
        self.assertEqual(blocks.cut(text, "sample", "swift"), "struct Shell {\n    let a = 1\n\n    let b = 2\n}\n")
        text = d("""
            var body: some View {
                // sample:else-begin
                // Text("Home")
                //     .padding()
                //
                // sample:else-end
            }
            """)
        self.assertEqual(blocks.cut(text, "sample", "swift"),
                         'var body: some View {\n    Text("Home")\n        .padding()\n\n}\n')
        # Dấu trong chuỗi nhiều dòng không phải dòng nguồn thật.
        bad = 'let s = """\n// sample:begin\nx\n// sample:end\n"""\n'
        with self.assertRaises(blocks.BlockError) as cm:
            blocks.cut(bad, "sample", "swift")
        self.assertEqual(cm.exception.line, 2)
        # Swift: chữ `sample:begin` dính code ⇒ lỗi (nghiêm hơn Markdown).
        with self.assertRaises(blocks.BlockError):
            blocks.cut("let a = 1 // sample:begin\n", "sample", "swift")
        # CRLF được giữ.
        self.assertEqual(blocks.cut("a\r\n// sample:begin\r\nb\r\n// sample:end\r\nc\r\n", "sample", "swift"),
                         "a\r\nc\r\n")


if __name__ == "__main__":
    unittest.main()
