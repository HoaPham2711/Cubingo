---
name: factory
description: Nhà máy agent — user giao MỘT mục tiêu hoặc nhiệm vụ nhiều bước ("/factory <mục tiêu>", "làm X tới xong", "tự lo việc Y"), phiên chính làm giám đốc - mở mission ledger, giao planner/critic lập kế hoạch, giao thợ theo vai (iOS, tooling/harness, research, release), verifier độc lập kiểm từng task, scribe ghi docs, chỉ dừng khi đạt DoD có bằng chứng hoặc chạm cổng con người. Cũng dùng cho "/factory status" và "/factory resume <id>". KHÔNG dùng cho việc nhỏ ≤ 3 lệnh.
argument-hint: "<mục tiêu> | status | resume <mission-id>"
---

# factory — sổ tay giám đốc

Bạn (phiên chính) là **giám đốc**. Bảng tự chủ: [autonomy.md](autonomy.md). Playbook + mẫu brief:
[playbooks.md](playbooks.md). Ledger: `tools/factory/mission.py` (trạng thái ở `.factory/missions/<id>/`).

Yêu cầu: $ARGUMENTS

## 0. Lệnh phụ
- `status` ⇒ `python3 tools/factory/mission.py list --all` + `show` mission active; trả lời ngắn, dừng.
- `resume <id>` ⇒ `python3 tools/factory/mission.py claim --mission <id>` (nhận làm giám đốc — bật cổng Stop cho
  phiên này) rồi `show --mission <id>`, tiếp tục từ task kế (bước 4).

## 1. Nhận việc (không hỏi lại user)
1. Nhắc lại mục tiêu một câu. Chọn playbook: `feature | fix | research | growth | analytics | release | ops`.
2. **Co giãn công sức**: việc ≤ 3 lệnh / 1 file ⇒ làm luôn, không mở mission. **Fix chỉ một task code** ⇒
   không mission, không planner/critic: làm theo vòng sửa (test đỏ → sửa → L1 → L2 một lần) ngay trong phiên.
   Câu hỏi thuần ⇒ trả lời.
3. Chỗ mơ hồ: tự chọn mặc định hợp lý nhất theo repo + memory, ghi vào ledger (`mission.py log "Giả định: …"`).
   Chỉ hỏi user khi đó là cổng trong [autonomy.md](autonomy.md).
4. Việc ghi code: phải ở nhánh feature trong `.claude/worktrees/<tên>` (EnterWorktree nếu đang ở checkout
   chính/`develop`). Research không cần nhánh.

## 2. Mở mission
```bash
python3 tools/factory/mission.py new --goal "<mục tiêu nguyên văn>" --playbook <pb> --branch "<nhánh>" --dod "<…>" --budget <n>
```
`--budget` lấy từ `budget` của planner (chưa có plan ⇒ ước số task code × 2,5 + 4). **Sau MỖI lượt Agent**:
`mission.py tick --what "<vai> <task> [vòng n]"` — ledger in `FACTORY-BUDGET` đúng lần đầu vượt ⇒ dừng lại xét
task nào đang lặp, `log` lý do, rồi mới giao tiếp.
Dòng `FACTORY-DIRECTOR <id> …` (chỉ `new`/`claim` in ra) nối phiên này với hook Stop
(`.claude/hooks/factory_stop_gate.py`): từ đây phiên **không dừng được** khi ledger chưa đạt DoD (tối đa 3 lần
nhắc mỗi phiên), trừ khi có cổng mở hoặc mission blocked. Phiên khác trong cùng checkout chỉ thấy tóm tắt
(SessionStart, `.claude/hooks/factory_context.py`), không bị chặn. Không ép dừng: thêm `--no-autopilot`.

## 3. Lập kế hoạch
1. Agent `factory-planner` với brief mẫu ở [playbooks.md](playbooks.md#brief-planner). Nhận JSON.
   `too_small: true` ⇒ `mission.py close --abandon "quá nhỏ, làm trực tiếp"` rồi làm luôn.
2. Agent `factory-critic` soát plan (gửi JSON plan, KHÔNG gửi suy nghĩ của bạn). `revise` ⇒ sửa theo
   `issues` (tự sửa hoặc gọi planner lần nữa, tối đa 1 vòng). `reject` ⇒ lập lại.
3. Ghi ledger — một lệnh mỗi task (đơn luồng, chỉ giám đốc ghi ledger):
   ```bash
   python3 tools/factory/mission.py add-task --title "…" --role <vai> --accept "…" --verify "…" [--depends T1]
   ```
   Cổng dự kiến của plan: ghi vào `mission.py log "Cổng dự kiến: …"` — **chưa** `gate open` (mở cổng = đang chờ user).
4. Playbook `feature`: task đầu là spec + plan commit riêng (quy ước dự án), `role: director` — giám đốc (hoặc
   thợ) viết, **`factory-critic` soát** (brief "Soi spec/plan task"), không qua verifier. Critic `ok` ⇒
   `set T1 --status verified --by director --evidence "critic ok: <tóm tắt>"`. Tối đa 1 vòng revise.
5. Mission đụng app ⇒ task cuối trước scribe là `role: factory-verifier` "Tích hợp L2" — nơi DUY NHẤT chạy
   `run_tests.py --full`.

## 4. Thi công — hai cách
- **Từng task, trong phiên** (mặc định khi ≤ 4 task hoặc task iOS): với mỗi task từ `mission.py next`:
  `set Tn --status doing` → Agent thợ (`subagent_type` = vai) với brief mẫu → `set Tn --status review` →
  Agent `factory-verifier` (brief: tiêu chí + lệnh verify + file; KHÔNG kèm báo cáo của thợ) →
  - PASS ⇒ `set Tn --status verified --by factory-verifier --evidence "<ledger_evidence>"`
  - FAIL ⇒ `set Tn --status failed --fail-class <class> [--fail-class …] --note "<findings>"` (mỗi `class` trong
    findings) → thợ sửa với **toàn bộ** findings (cả `instances`, `fix_strategy`) → verifier lại với brief "vòng
    kiểm lại" kèm findings cũ ([playbooks.md](playbooks.md#brief-verifier)). `debt` của verifier ⇒ `log`, không gửi thợ.
  - **`FACTORY-ESCALATE`** (cùng lớp FAIL lần 2) ⇒ KHÔNG gửi thợ vá tiếp. Chọn một: (a) `amend accept` thành bất
    biến + test thuộc tính/fuzz phủ cả lớp rồi giao lại, (b) thu hẹp phạm vi task (phần khó thành task sau),
    (c) `gate open --kind decision`. Task spec/plan: escalate ⇒ chốt spec ở mức quyết định + bất biến, chuyển chi
    tiết còn lại thành acceptance của task code.
  - **Trần 2 lần FAIL**: ledger tự chuyển `blocked` ở FAIL thứ 2 ⇒ không giao thợ vá lần 3. Giám đốc chọn
    (a)/(b)/(c) ở trên hoặc mở cổng `decision` hỏi user; trong lúc đó làm task khác. Mở lại task blocked chỉ khi
    đã đổi cách — "thử lại y như cũ" là đốt lượt.
- **Workflow `factory-execute`** (nhiều task, có nhóm song song được): gọi Workflow tên `factory-execute`
  với `args = {mission: <JSON của mission.py show --json>}`. Workflow trả kết quả từng task; giám đốc ghi
  ledger từ kết quả (verified/failed/blocked + evidence) bằng đúng `ledger_commands` nó trả — dòng ĐẦU là
  `mission.py tick <agent_runs>` (mọi lượt agent trong workflow, kể cả fallback/vòng sửa), đừng bỏ.
  Task đụng build iOS luôn tuần tự.
- Fan-out song song chỉ cho việc ĐỌC (research, review). Ghi code: một người một tập file.

## 5. Tích hợp
1. App đổi ⇒ L2 chạy **đúng một lần** trong task "Tích hợp L2" của verifier (`run_tests.py --full` + lint i18n
   và ảnh iPhone + iPad nếu UI). Giám đốc KHÔNG chạy lại L2/L1/mutate — đọc evidence của verifier. Chỉ chạy lại
   L2 khi có commit sửa code SAU lần L2 đó. Không chạy `tools/i18n/verify_catalog.py` trong mission (chỉ có `en`;
   cổng tự bật khi `app.config.toml` `[i18n] languages` có thêm ngôn ngữ).
2. Trước merge (L3) ⇒ workflow `factory-review`. Đổi tooling của chính template ⇒ thêm
   `tools/template/selfcheck.sh` vào L3.
3. **Đóng hồ sơ TRƯỚC commit cuối**: làm §7 bước 1–3 (report, critic, `close`) ngay tại đây, rồi commit trên
   nhánh feature theo skill `commit-convention` (chỉ add file của mission) **kèm `.factory/missions/<id>/`**
   (`mission.json`, `plan.json`, `report.md` thuộc git theo thiết kế; `artifacts/` không commit). `close` in
   `FACTORY-UNTRACKED` ⇒ chưa add xong, đừng mở PR. Mission không có nhánh code (research) ⇒ commit hồ sơ lên
   nhánh làm việc hiện tại hoặc PR nhỏ.
4. Merge PR vào `develop` (cổng `push`) ⇒ hook `.claude/hooks/post_merge_sync_develop.py` tự fast-forward
   `develop` local (`tools/dev/sync_develop.py`) và trả `[post-merge] SYNC-DEVELOP …`. `FAIL` ⇒ báo user lý do,
   KHÔNG stash/reset hộ. Merge ngoài `gh pr merge` (nút app, web GitHub) ⇒ tự chạy `python3 tools/dev/sync_develop.py`.

## 6. Cổng con người
Tới bước thuộc lớp "cổng" ([autonomy.md](autonomy.md)):
```bash
python3 tools/factory/mission.py gate open --kind <push|deploy|asc|spend|device|send|decision|publish|delete> --ask "<một câu>"
```
rồi kết thúc lượt với đúng câu hỏi đó. Khi user trả lời: `gate approve G<n>` / `gate reject G<n>`, làm tiếp.
Thử trên device thật: mở cổng `device` kèm checklist, phần việc khác vẫn chạy.

## 7. Kết thúc
Bước 1–3 chạy TRƯỚC commit cuối/merge (§5.3) để ledger `done` + report vào cùng PR. Lỡ merge rồi mới close ⇒
commit bổ sung `.factory/missions/<id>/` qua PR nhỏ.
1. Agent `factory-scribe` (mission id) ⇒ ROADMAP, memory, memory vai, Retro + **trả nội dung report**; giám đốc
   ghi `.factory/missions/<id>/report.md` (Claude Code chặn subagent ghi file report).
2. Agent `factory-critic` soát report trước khi gửi (số có nguồn, không nói quá).
3. `python3 tools/factory/mission.py close` (từ chối nếu chưa đạt DoD — đó là tín hiệu thật, đừng lách bằng
   `--abandon` trừ khi bỏ thật).
4. Báo user: kết quả theo DoD + bằng chứng, chưa kiểm/chưa làm, cổng đang chờ, chi phí (số agent), đề xuất
   Retro. Ngắn.

## Luật giám đốc
- Không tin báo cáo của thợ: chỉ verifier đánh `verified` (task spec: giám đốc theo kết quả critic). Chỉ giám đốc ghi ledger.
- **Kiểm chứng mỗi thứ một lần**: thợ L1 theo class; verifier L1 + tối đa 3 mutant/task; L2 một lần ở task
  cuối. Chạy L2 ở nhiều vai và poll `sleep` là hai nguồn đốt lượt lớn nhất.
- Brief thợ/verifier luôn kèm: "lệnh dài chạy Bash foreground `timeout: 600000`, không chạy nền rồi poll".
- Brief tự đủ (thợ không thấy hội thoại): mục tiêu, tiêu chí, file, ràng buộc, cái đã loại trừ.
- Ngân sách: theo `--budget` (công thức ở trên; không có plan ⇒ 15). Đếm bằng `tick` (cả lượt trong workflow —
  `ledger_commands` có sẵn dòng tick), không đếm nhẩm. **Vượt = mốc XÉT LẠI, không phải trần**: cùng lớp lỗi
  lặp ⇒ đổi cách (escalate); chỉ là phạm vi lớn hơn ước tính (plan thêm task, nhiều vòng verify hợp lệ) ⇒
  `mission.py budget --set <N> --why "…"` rồi làm tiếp — KHÔNG cắt việc/bỏ task cho vừa ngân sách.
- **Định tuyến model**: bậc mỗi vai ở frontmatter `.claude/agents/`; bảng `ROLE_TIER` trong workflow phải khớp —
  `tools/factory/lint_harness.py` gác. Vai cơ học dùng model rẻ (đã đặt trong frontmatter). Task khó bất thường
  với một vai sonnet ⇒ giao bằng Agent tool kèm `model: "opus"`.
- Vòng sửa thứ 2 cùng một lớp lỗi là tín hiệu cách làm sai, không phải thợ kém — đổi tiêu chí/phạm vi.
- Nhắc trong hội thoại không thay được hook: luật "không bao giờ" nằm ở hook (`guard_*` trong `.claude/hooks/`).
- Playbook `growth` dùng `growth-marketer` (skill `release-aso`), `analytics` dùng `data-analyst` (skill
  `product-analytics`); số liệu thật cần khoá của user — thiếu khoá thì báo user, không giả lập số liệu. Bản tin tuần
  đa vai: workflow `factory-weekly`.
