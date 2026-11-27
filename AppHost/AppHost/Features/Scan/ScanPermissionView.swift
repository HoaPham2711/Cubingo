import SwiftUI
import UIKit

/// Màn nào hiện theo quyền camera.
enum ScanPermissionModel {
    enum Screen: Equatable { case explain, denied, camera }

    static func screen(for status: ScanCameraStatus) -> Screen {
        switch status {
        case .notDetermined: return .explain
        case .denied: return .denied
        case .authorized: return .camera
        }
    }
}

/// Đích `.scan`: giải thích trước lần xin quyền đầu, màn "camera tắt" khi bị từ chối, còn lại là màn quét.
struct ScanEntryView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    @State private var status: ScanCameraStatus
    @Environment(\.scenePhase) private var scenePhase

    init(flow: FlowModel, deps: FlowDependencies) {
        self.flow = flow
        self.deps = deps
        _status = State(initialValue: deps.cameraAuth.status())
    }

    var body: some View {
        Group {
            switch ScanPermissionModel.screen(for: status) {
            case .camera:
                ScanView(flow: flow, deps: deps)
            case .explain, .denied:
                ScanPermissionView(screen: ScanPermissionModel.screen(for: status),
                                   onAllow: {
                                       Task {
                                           _ = await deps.cameraAuth.request()
                                           status = deps.cameraAuth.status()
                                       }
                                   },
                                   onManual: { flow.path.append(.review(manual: true)) })
            }
        }
        // Quay lại từ Settings (bật camera) ⇒ đọc lại quyền.
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { status = deps.cameraAuth.status() }
        }
    }
}

struct ScanPermissionView: View {
    let screen: ScanPermissionModel.Screen
    let onAllow: () -> Void
    let onManual: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: screen == .denied ? "video.slash.fill" : "camera.fill")
                .scaledFont(size: 56, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.accent)
            if screen == .denied {
                Text("Camera is off for \(AppConfig.current.displayName)")
                    .scaledFont(size: 26, weight: .heavy, design: .rounded)
                    .multilineTextAlignment(.center)
                Text("Turn it on in Settings to scan your cube, or enter the colors yourself.")
                    .scaledFont(size: 17, weight: .medium, design: .rounded)
                    .foregroundColor(DSColor.textSecondary)
                    .multilineTextAlignment(.center)
            } else {
                Text("We use the camera to read your cube's colors. Nothing leaves your phone.")
                    .scaledFont(size: 20, weight: .bold, design: .rounded)
                    .multilineTextAlignment(.center)
            }
            Spacer()
            if screen == .denied {
                Button("Open Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                }
                .buttonStyle(StyleThickButton())
            } else {
                Button("Allow camera", action: onAllow)
                    .buttonStyle(StyleThickButton())
            }
            Button("Enter colors manually", action: onManual)
                .buttonStyle(StyleThickButton(kind: .secondary))
        }
        .foregroundColor(DSColor.textPrimary)
        .padding(24)
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity)
        .styleBackground()
        .trackScreen("scan_permission")
    }
}
