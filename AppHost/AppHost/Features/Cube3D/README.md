# Cube3D

`Cube3DScene` (thuần, `simd`) là nguồn sự thật: 26 khối con, áp bước bằng phép quay nguyên + quaternion; test chứng minh
`scene.facelets()` luôn bằng facelet sau cùng dãy bước. `Cube3DView` (RealityKit, `RealityView` + camera ảo) chỉ vẽ
cảnh đó: dừng ở `state`, có `Cube3DAnimation` mới thì dựng trạng thái trước bước rồi quay lớp (bước kép = hai nấc).
`highlight` làm sáng nhãn của lớp sắp quay + mũi tên cong (`Cube3DArrow`). Kiểm bằng mắt qua route `mode`/`guide`.
