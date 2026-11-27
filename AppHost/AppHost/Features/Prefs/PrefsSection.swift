import SwiftUI

/// Nhóm "Solving" trong Settings: tốc độ hoạt ảnh, rung, hiện ký hiệu bước.
struct PrefsSection: View {
    @ObservedObject var prefs: PrefsStore

    var body: some View {
        Section {
            Picker("Animation speed", selection: $prefs.speed) {
                ForEach(PrefsSpeed.allCases, id: \.self) { s in
                    Text(s.label).tag(s)
                }
            }
            Toggle("Haptics", isOn: $prefs.haptics)
            Toggle("Show move notation", isOn: $prefs.showNotation)
        } header: {
            Text("Solving")
        }
        .tint(DSColor.accent)
    }
}
