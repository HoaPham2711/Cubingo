import AVFoundation

enum ScanCameraStatus: Equatable { case notDetermined, authorized, denied }

/// Quyền camera, đưa vào qua closure để test/Simulator thay được.
struct ScanCameraAuth {
    var status: () -> ScanCameraStatus
    var request: () async -> Bool

    /// AVFoundation thật; `restricted` coi như `denied`.
    static let live = ScanCameraAuth(
        status: {
            switch AVCaptureDevice.authorizationStatus(for: .video) {
            case .authorized: return .authorized
            case .notDetermined: return .notDetermined
            default: return .denied
            }
        },
        request: { await AVCaptureDevice.requestAccess(for: .video) })
}
