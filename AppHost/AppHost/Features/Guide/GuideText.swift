import Foundation

/// Mọi chữ của màn chỉ bước. Màu luôn là THAM SỐ (tên đo từ khối thật qua `CubePalette`), không nối chuỗi.
enum GuideText {
    /// Câu của một bước, nhìn từ phía trước (spec 5.6).
    static func sentence(_ m: CubeMove) -> String {
        switch (m.axis, m.turns) {
        case (.face(.r), 1): return String(localized: "Turn the right side up")
        case (.face(.r), 3): return String(localized: "Turn the right side down")
        case (.face(.r), _): return String(localized: "Turn the right side twice")
        case (.face(.l), 1): return String(localized: "Turn the left side down")
        case (.face(.l), 3): return String(localized: "Turn the left side up")
        case (.face(.l), _): return String(localized: "Turn the left side twice")
        case (.face(.u), 1): return String(localized: "Turn the top to the left")
        case (.face(.u), 3): return String(localized: "Turn the top to the right")
        case (.face(.u), _): return String(localized: "Turn the top twice")
        case (.face(.d), 1): return String(localized: "Turn the bottom to the right")
        case (.face(.d), 3): return String(localized: "Turn the bottom to the left")
        case (.face(.d), _): return String(localized: "Turn the bottom twice")
        case (.face(.f), 1): return String(localized: "Turn the front clockwise")
        case (.face(.f), 3): return String(localized: "Turn the front counterclockwise")
        case (.face(.f), _): return String(localized: "Turn the front twice")
        // Nhìn từ PHÍA TRƯỚC (người mới hay tự nhìn vào mặt sau ⇒ xoay ngược chiều).
        case (.face(.b), 1): return String(localized: "Turn the back counterclockwise, as seen from the front")
        case (.face(.b), 3): return String(localized: "Turn the back clockwise, as seen from the front")
        case (.face(.b), _): return String(localized: "Turn the back twice")
        case (.x, 1): return String(localized: "Roll the whole cube forward so the front goes up")
        case (.x, 3): return String(localized: "Roll the whole cube back so the front goes down")
        case (.x, _): return String(localized: "Roll the whole cube forward twice")
        case (.y, 1): return String(localized: "Turn the whole cube to the left")
        case (.y, 3): return String(localized: "Turn the whole cube to the right")
        case (.y, _): return String(localized: "Turn the whole cube around")
        case (.z, 1): return String(localized: "Tip the whole cube to the right")
        case (.z, 3): return String(localized: "Tip the whole cube to the left")
        case (.z, _): return String(localized: "Tip the whole cube upside down")
        }
    }

    static func stageTitle(_ k: SolverStageKind, base: String, top: String) -> String {
        switch k {
        case .cross: return String(localized: "\(base) cross")
        case .corners: return String(localized: "\(base) corners")
        case .middle: return String(localized: "Middle layer")
        case .topCross: return String(localized: "\(top) cross")
        case .topFace: return String(localized: "\(top) face")
        case .topCorners: return String(localized: "\(top) corners")
        case .topEdges: return String(localized: "\(top) edges")
        }
    }

    static func stageHeader(_ k: SolverStageKind, base: String, top: String) -> String {
        let title = stageTitle(k, base: base, top: top)
        return String(localized: "Stage \(k.rawValue) · \(title)")
    }

    /// Một câu mục tiêu mỗi chặng (≤ 70 ký tự).
    static func stageGoal(_ k: SolverStageKind, base: String, top: String) -> String {
        switch k {
        case .cross: return String(localized: "Make a \(base) cross on the bottom that matches the side centers")
        case .corners: return String(localized: "Finish the \(base) layer by placing its four corners")
        case .middle: return String(localized: "Fill in the four edges of the middle layer")
        case .topCross: return String(localized: "Make a \(top) cross on top")
        case .topFace: return String(localized: "Turn the whole top \(top)")
        case .topCorners: return String(localized: "Move the top corners to their right spots")
        case .topEdges: return String(localized: "Move the last edges into place to finish the cube")
        }
    }

    static func hold(top: String, front: String) -> String {
        String(localized: "Hold: \(top) on top, \(front) facing you")
    }

    /// Lý do của một nhóm bước. `top` = màu đỉnh (đối diện `base`).
    static func reason(_ r: SolverReason, palette: CubePalette, base: CubeColor, top: CubeColor) -> String {
        let b = palette.name(base), t = palette.name(top)
        switch r {
        case let .hold(top, front):
            return hold(top: palette.name(top), front: palette.name(front))
        case let .makeDaisy(edge):
            let e = palette.name(edge)
            return String(localized: "Bring the \(b)-\(e) edge up next to the \(t) center")
        case let .dropToCross(edge):
            let e = palette.name(edge)
            return String(localized: "Line up the \(b)-\(e) edge over its center, then turn that side twice")
        case .liftCorner:
            return String(localized: "Lift the stuck corner up to the top layer")
        case let .placeCorner(c1, c2):
            let n1 = palette.name(c1), n2 = palette.name(c2)
            return String(localized: "Put the \(b)-\(n1)-\(n2) corner above its spot, then repeat")
        case let .insertEdge(c1, c2, toRight):
            let n1 = palette.name(c1), n2 = palette.name(c2)
            return toRight
                ? String(localized: "Line up the \(n1)-\(n2) edge, then drop it in to the right")
                : String(localized: "Line up the \(n1)-\(n2) edge, then drop it in to the left")
        case .popEdge:
            return String(localized: "Pop out the wrong edge so it can go back in the right way")
        case .makeTopCross:
            return String(localized: "Use the cross maker until a \(t) cross appears")
        case .orientTopCorners:
            return String(localized: "Repeat Sune until the whole top is \(t)")
        case .placeTopCorners:
            return String(localized: "Keep the matching corners at the back, then cycle the corners")
        case .placeTopEdges:
            return String(localized: "Keep the finished side at the back, then cycle the edges")
        case .alignTop:
            return String(localized: "Turn the top until the corners match the sides")
        }
    }

    static func algorithmName(_ a: SolverAlgorithm) -> String {
        switch a {
        case .rightTrigger: return String(localized: "Right trigger")
        case .rightInsert: return String(localized: "Right insert")
        case .leftInsert: return String(localized: "Left insert")
        case .crossMaker: return String(localized: "Cross maker")
        case .sune: return String(localized: "Sune")
        case .cornerCycle: return String(localized: "Corner cycle")
        case .edgeCycle: return String(localized: "Edge cycle")
        }
    }

    static func progress(step: Int, of total: Int) -> String {
        String(localized: "\(step) / \(total)")
    }

    static func quickProgress(step: Int, of total: Int) -> String {
        String(localized: "Move \(step) / \(total)")
    }
}
