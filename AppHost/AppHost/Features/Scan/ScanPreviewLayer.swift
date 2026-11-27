import AVFoundation
import SwiftUI
import UIKit

/// Lớp xem trước camera (aspect fill), ảnh đứng.
struct ScanPreviewLayer: UIViewRepresentable {
    let session: AVCaptureSession

    /// Kích thước ảnh camera đã xoay đứng (preset 1920×1080).
    static let bufferSize = CGSize(width: 1080, height: 1920)

    /// Khung lấy mẫu (`ScanSampler.frameRect`) đổi sang toạ độ của view hiển thị ảnh theo aspect fill — cùng phép tính
    /// với `AVCaptureVideoPreviewLayer.resizeAspectFill`.
    static func frameRect(in viewSize: CGSize) -> CGRect {
        let b = bufferSize
        let scale = max(viewSize.width / b.width, viewSize.height / b.height)
        let shown = CGSize(width: b.width * scale, height: b.height * scale)
        let origin = CGPoint(x: (viewSize.width - shown.width) / 2, y: (viewSize.height - shown.height) / 2)
        let f = ScanSampler.frameRect(in: b)
        return CGRect(x: origin.x + f.minX * scale, y: origin.y + f.minY * scale,
                      width: f.width * scale, height: f.height * scale)
    }

    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.previewLayer.session = session
        v.previewLayer.videoGravity = .resizeAspectFill
        if let c = v.previewLayer.connection, c.isVideoRotationAngleSupported(90) { c.videoRotationAngle = 90 }
        return v
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
}
