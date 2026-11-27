# Flow

Luồng một chiều của Cubingo: chọn khối → quét → kiểm tra → chọn cách giải → chỉ bước → xong. `FlowModel` giữ
`path` của `NavigationStack` gốc (`HomeView`); `FlowDependencies` dựng một lần ở `AppHostApp`.

| Route preview | Màn |
|---|---|
| `home` | Màn chọn khối (`FlowPickerView`) |
| `settings` | Sheet Settings có nhóm "Solving" (`PrefsSection`) |
