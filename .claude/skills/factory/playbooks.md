# Playbook + mẫu brief của nhà máy

## Bảng chọn playbook

| Playbook | Khi nào | Chuỗi vai | Cổng thường gặp | Xong khi |
|---|---|---|---|---|
| `feature` | màn mới, khối lõi mới, thay đổi kiến trúc | planner → critic → (spec+plan: critic soát, commit) → ios/platform-engineer ×n → verifier mỗi task (L1) → ui-reviewer (UI) → verifier "Tích hợp L2" (một lần) → scribe | push develop, device | DoD + L2 xanh + ảnh iPhone/iPad (UI) + ROADMAP |
| `fix` | lỗi có tái hiện được, ≥ 2 task code (fix một task ⇒ KHÔNG mission, làm thẳng theo vòng sửa) | tái hiện → test đỏ → engineer sửa → verifier (L1 + mutate ≤3) → verifier "Tích hợp L2" | device nếu chỉ tái hiện trên máy | test đỏ→xanh, L2 |
| `research` | câu hỏi cần nguồn | workflow `factory-research` → critic soát kết luận → scribe lưu docs/research/ | — | báo cáo có nguồn, mâu thuẫn được nêu |
| `growth` | ASO, copy, quảng cáo, thử nghiệm tăng trưởng | planner → `growth-marketer` (skill `release-aso`: sửa `store/`, `aso.py lint`, `aso.py plan`) + `data-analyst` (số đo) → verifier (lint/plan chạy được) → critic soát chữ + giả thuyết | asc, spend | kế hoạch có giả thuyết + cách đo; plan ASO nguyên văn cho user; không đẩy gì lên ASC (`apply` chỉ sau xác nhận) |
| `analytics` | câu hỏi sản phẩm bằng số | `data-analyst` (skill `product-analytics`: `tools/analytics` → digest → báo cáo) → critic soát số khi kết luận quan trọng | — (khoá do user cấp; thiếu khoá = báo user, không bịa số) | trả lời có số + nguồn + độ tin cậy; nguồn thiếu nêu rõ |
| `release` | "ra bản", hotfix | release-manager kiểm → giám đốc đi từng cổng theo `docs/RELEASE.md` | push, asc | bản nộp được: build lên ASC qua `build` → `release-plan` → `apply` của công cụ ASO (skill `release-aso`, mỗi bước ghi là cổng `asc`); user tự bấm nộp review |
| `ops` | harness, tooling, dọn nợ kỹ thuật không đổi hành vi app | platform-engineer → verifier → `lint_harness.py` (+ `tools/template/selfcheck.sh --quick` khi đụng tooling template) | — | test + lint xanh |

Mission nhiều mảng: playbook chính = mảng có thay đổi lớn nhất; task của các vai khác vẫn nằm trong cùng mission.

<a id="brief-planner"></a>
## Brief planner
```
Mission <id>, playbook dự kiến <pb>. Mục tiêu nguyên văn của user: "<…>".
Ràng buộc đã biết: <nhánh, hạn, giả định giám đốc đã chọn>.
Đã loại trừ: <…>.
Trả JSON đúng mẫu "Ra" của bạn. Dùng `python3 tools/factory/roadmap.py debt --since <ngày>` thay vì đọc cả ROADMAP.
```

## Brief critic
```
Soát PLAN sau cho mission <id> (mục tiêu: "<…>"). Chỉ báo lỗi có hậu quả, không style.
<JSON plan>
```
Soát spec/plan task (thay verifier):
```
Soi spec/plan task T1 của mission <id> theo mục "Soi spec/plan task" của bạn. File: <spec.md>, <plan.md>.
Tiêu chí T1: <…>. Trả JSON đúng mẫu "Ra".
```

## Brief thợ (ios-engineer / platform-engineer / researcher)
```
Mission <id>, task <Tn>: <title>.
Tiêu chí (phải đạt hết): 1. … 2. …
Lệnh verifier sẽ chạy: <…>
File trong phạm vi: <…>   Ngoài phạm vi: <…>
Kiểm chứng gọn: L1 theo class (`run_tests.py FooTests`); KHÔNG `--full`, KHÔNG `verify_catalog.py`, KHÔNG
`mutate.py` (verifier làm). Lệnh dài: Bash foreground `timeout: 600000`, không chạy nền rồi poll `sleep`/`until`.
Ràng buộc: <invariant/quy ước liên quan, nhánh hiện tại>
[Vòng sửa] Verifier báo FAIL: <findings nguyên văn, cả instances + fix_strategy>
[Vòng sửa] Sửa CẢ LỚP: mọi `instances`, rồi tự grep thêm chỗ cùng `class` mà verifier có thể sót; `fix_strategy`
           là bất biến/test thuộc tính ⇒ viết test đó trước, đừng vá từng ca. Báo cáo liệt kê mọi chỗ đã rà.
Trả báo cáo đúng mẫu "Ra" của bạn. Không commit, không push.
```

<a id="brief-verifier"></a>
## Brief verifier
```
Kiểm độc lập task <Tn> của mission <id>. Bạn không có báo cáo của thợ — tự kiểm.
Tiêu chí: 1. … 2. …
Lệnh verify: <…>
Phạm vi: <file/diff base: `git diff <base>...HEAD -- <paths>` hoặc chưa commit: `git diff`>
Mutant tối đa 3 cho bất biến quan trọng nhất. KHÔNG `--full` (trừ task "Tích hợp L2"), KHÔNG `verify_catalog.py`.
Lệnh dài: Bash foreground `timeout: 600000`, không chạy nền rồi poll.
[Task "Tích hợp L2"] `python3 tools/dev/run_tests.py --full` đúng một lần (+ lint i18n, ảnh iPhone/iPad nếu UI).
[Vòng kiểm lại] Finding vòng trước: <JSON findings>. Theo luật "Quét cạn" mục 4 của bạn: lỗi mới ngoài diff
               sửa + ngoài các lớp trên chỉ FAIL nếu blocker/major có repro; còn lại vào `debt`.
Quét cạn: mỗi finding có `class` + mọi `instances`; không dừng ở lỗi đầu.
Trả JSON đúng mẫu "Ra" của bạn.
```

## Brief scribe
```
Mission <id> đã xong phần thi công. Ledger: `python3 tools/factory/mission.py show --mission <id>`.
Base của nhánh: <sha>. Cập nhật ROADMAP/lessons/memory/memory vai theo vai trò của bạn; TRẢ toàn văn report trong
mục "## Nội dung report.md" (bạn không ghi được file report — giám đốc ghi), kèm Retro.
```

## Workflow đặt tên
- `/factory-execute` — chạy task graph (giám đốc truyền `args.mission`).
- `/factory-review` — review nhánh 4 lăng kính + phản biện (cổng L3).
- `/factory-research` — research nhiều góc (truyền `args.question`).
- `/factory-eval` — eval hành vi các vai nhà máy (chạy khi đổi model hoặc sửa prompt agent).
