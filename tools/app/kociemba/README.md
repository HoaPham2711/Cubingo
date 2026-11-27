# Bảng tra Kociemba

`gen_tables.sh` biên dịch (`swiftc -O`) chính các file nguồn của app — `Cube{Face,Move,Geometry,Facelets,Cubies}.swift`,
`SolverKociemba{Coords,Tables}.swift` — cùng `main.swift`, rồi ghi
`AppHost/AppHost/Features/Solver/Resources/kociemba-tables.bin` (~4,2 MB, commit cùng mã). Tool đọc lại file bằng code
nạp của app trước khi ghi.

```bash
bash tools/app/kociemba/gen_tables.sh
```

- **Khi nào sinh lại:** chỉ khi đổi định nghĩa toạ độ, thứ tự bước, hoặc định dạng file (`SolverKociembaTables`). Đổi
  xong chạy `tools/dev/run_tests.py SolverKociembaTablesTests` — test tính lại bảng bước ngẫu nhiên và so với file.
- **Nguồn thuật toán:** mô tả công khai của thuật toán hai pha (toạ độ twist/flip/slice, bảng bước, bảng cắt tỉa
  IDA*). Mã tự viết; không chép mã nguồn có giấy phép copyleft (GPL/LGPL).
