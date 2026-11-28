import AVFoundation
import QuartzCore

/// Camera sau cho màn quét: `AVCaptureVideoDataOutput` BGRA đứng (xoay 90°), lấy mẫu trên queue riêng, phát `samples`
/// ≤ 15 lần/giây. Simulator không có camera ⇒ phát lưới của `ScanPreviewSeed` (đi hết luồng, chụp ảnh UI).
@MainActor
final class ScanCamera: ObservableObject {
    @Published private(set) var samples: [CubeRGB] = []

    let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "scan.camera")
    private var sink: ScanCameraSink?
    private var configured = false
    #if targetEnvironment(simulator)
    private var seedTask: Task<Void, Never>?
    private var seedFrame: [CubeRGB] = ScanPreviewSeed.image(ScanProtocol.cube3[0])
    #endif

    /// Có lớp xem trước camera thật (device) hay không (Simulator: khung giả).
    var hasLivePreview: Bool {
        #if targetEnvironment(simulator)
        return false
        #else
        return true
        #endif
    }

    func start() {
        #if targetEnvironment(simulator)
        startSeed()
        #else
        configureIfNeeded()
        let session = session
        queue.async { if !session.isRunning { session.startRunning() } }
        #endif
    }

    func stop() {
        #if targetEnvironment(simulator)
        seedTask?.cancel()
        seedTask = nil
        #else
        let session = session
        queue.async { if session.isRunning { session.stopRunning() } }
        #endif
    }

    /// Bước quét hiện tại chờ — chỉ nguồn giả trên Simulator dùng (đổi ảnh sau 0,8 s như người xoay khối).
    func expect(_ step: ScanStep) {
        #if targetEnvironment(simulator)
        expectFrame(ScanPreviewSeed.image(step))
        #endif
    }

    /// Quét kiểm tra một mặt (lưới theo thứ tự đọc của mặt).
    func expect(_ face: CubeFace) {
        #if targetEnvironment(simulator)
        expectFrame(ScanPreviewSeed.checkImage(face))
        #endif
    }

    #if targetEnvironment(simulator)
    /// Có giá trị ⇒ nguồn giả của CAMERA NÀY luôn phát đúng khung này (giữ trạng thái để chụp ảnh UI).
    private var frozenFrame: [CubeRGB]?

    func freezeSeed(_ frame: [CubeRGB]) { frozenFrame = frame }

    private func expectFrame(_ next: [CubeRGB]) {
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 800_000_000)
            self?.seedFrame = next
        }
    }
    #endif

    private func configureIfNeeded() {
        guard !configured else { return }
        configured = true
        session.beginConfiguration()
        session.sessionPreset = .hd1920x1080
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device), session.canAddInput(input) else {
            session.commitConfiguration()
            return
        }
        session.addInput(input)
        let output = AVCaptureVideoDataOutput()
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.alwaysDiscardsLateVideoFrames = true
        let sink = ScanCameraSink { [weak self] s in
            Task { @MainActor in self?.samples = s }
        }
        self.sink = sink
        output.setSampleBufferDelegate(sink, queue: queue)
        if session.canAddOutput(output) { session.addOutput(output) }
        if let c = output.connection(with: .video), c.isVideoRotationAngleSupported(90) { c.videoRotationAngle = 90 }
        session.commitConfiguration()
    }

    #if targetEnvironment(simulator)
    private func startSeed() {
        seedTask?.cancel()
        seedTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                self.samples = self.frozenFrame ?? self.seedFrame
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
        }
    }
    #endif
}

/// Delegate trên queue camera: lấy mẫu, bỏ bớt khung để ≤ 15 lần/giây.
final class ScanCameraSink: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    private let onSamples: ([CubeRGB]) -> Void
    private var last: CFTimeInterval = 0

    init(onSamples: @escaping ([CubeRGB]) -> Void) {
        self.onSamples = onSamples
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        let now = CACurrentMediaTime()
        guard now - last >= 1.0 / 15, let pb = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        last = now
        onSamples(ScanSampler.sample(pb, n: 3))
    }
}
