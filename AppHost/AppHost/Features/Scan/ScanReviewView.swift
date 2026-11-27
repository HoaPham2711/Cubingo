import SwiftUI

/// Màn kiểm tra màu (sau quét) / nhập tay: sơ đồ khối, chạm ô để đổi màu, một thông báo lỗi mỗi lần.
struct ScanReviewView: View {
    @ObservedObject var flow: FlowModel
    let deps: FlowDependencies
    @StateObject private var model: ScanReviewModel
    @State private var outcome: ScanReviewOutcome
    @State private var editing: Int?

    init(flow: FlowModel, deps: FlowDependencies, manual: Bool) {
        self.flow = flow
        self.deps = deps
        let m = (!manual ? flow.scan.map { ScanReviewModel(scan: $0) } : nil)
            ?? ScanReviewModel(manualCenters: ScanReviewModel.defaultManualCenters)
        _model = StateObject(wrappedValue: m)
        _outcome = State(initialValue: m.validate())
    }

    private var isGood: Bool {
        switch outcome {
        case .ok, .autoFixed: return true
        default: return false
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text(model.isManual ? "Enter your cube's colors" : "Check the colors")
                    .scaledFont(size: 28, weight: .heavy, design: .rounded)
                    .foregroundColor(DSColor.textPrimary)
                Text(model.isManual ? "Tap a square, then pick its color. Tap a center to change it."
                                    : "Tap any square that looks wrong to fix it.")
                    .scaledFont(size: 16, weight: .medium, design: .rounded)
                    .foregroundColor(DSColor.textSecondary)
                ScanNetView(facelets: model.facelets, palette: model.palette, suspects: model.suspects) { i in
                    editing = i
                }
                .frame(maxWidth: .infinity)
                if let editing { picker(for: editing) }
                message
                if isGood {
                    Button("Continue") { continueTapped() }
                        .buttonStyle(StyleThickButton())
                }
                if !model.isManual {
                    Button("Scan again") { flow.path.removeLast() }
                        .buttonStyle(StyleThickButton(kind: .secondary))
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .readableContentWidth()
        }
        .styleBackground()
        .navigationBarTitleDisplayMode(.inline)
        .trackScreen("scan_review")
    }

    private var message: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: isGood ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundColor(isGood ? DSColor.statusGood : DSColor.statusWarning)
            Text(ScanReviewText.message(outcome, palette: model.palette))
                .foregroundColor(DSColor.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .scaledFont(size: 17, weight: .semibold, design: .rounded)
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .styleCard()
    }

    @ViewBuilder
    private func picker(for index: Int) -> some View {
        let isCenter = ScanReviewModel.isCenter(index)
        VStack(alignment: .leading, spacing: 10) {
            Text(isCenter ? "Pick the center's color" : "Pick a color")
                .scaledFont(size: 15, weight: .bold, design: .rounded)
                .foregroundColor(DSColor.textSecondary)
            if isCenter {
                if model.isManual {
                    let face = CubeFace(rawValue: index / 9)!
                    swatches(model.centerChoices(for: face).map { ($0.rawValue, $0.standardRGB, $0.localized(shade: nil)) }) { key in
                        if let name = CubeColorName(rawValue: key) { model.setCenter(face, to: name) }
                    }
                } else {
                    Text("Centers set the colors — fix the other squares instead.")
                        .scaledFont(size: 15, weight: .medium, design: .rounded)
                        .foregroundColor(DSColor.textSecondary)
                }
            } else {
                swatches(CubeColor.all.map { (String($0.raw), model.palette.rgb($0), model.palette.name($0)) }) { key in
                    if let raw = UInt8(key) { model.set(index, to: CubeColor(raw: raw)) }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .styleCard()
    }

    private func swatches(_ items: [(key: String, rgb: CubeRGB, name: String)], pick: @escaping (String) -> Void) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 52), spacing: 10)], spacing: 10) {
            ForEach(items, id: \.key) { item in
                Button {
                    pick(item.key)
                    revalidate()
                } label: {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(Color(.sRGB, red: item.rgb.r, green: item.rgb.g, blue: item.rgb.b, opacity: 1))
                        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.black.opacity(0.15)))
                        .frame(height: 52)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text(item.name))
            }
        }
    }

    private func revalidate() {
        editing = nil
        outcome = model.validate()
    }

    private func continueTapped() {
        switch outcome {
        case .ok(let f), .autoFixed(let f): flow.didReview(f, palette: model.palette, white: model.whiteReference)
        default: break
        }
    }
}
