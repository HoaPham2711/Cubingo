import Foundation

/// Các công thức có tên của phương pháp người mới — lặp lại nhất quán để người dùng học thuộc (spec 5.7).
enum SolverAlgorithm: CaseIterable {
    case rightTrigger, rightInsert, leftInsert, crossMaker, sune, cornerCycle, edgeCycle

    var moves: [CubeMove] {
        let s: String
        switch self {
        case .rightTrigger: s = "R U R' U'"
        case .rightInsert: s = "U R U' R' U' F' U F"
        case .leftInsert: s = "U' L' U L U F U' F'"
        case .crossMaker: s = "F R U R' U' F'"
        case .sune: s = "R U R' U R U2 R'"
        case .cornerCycle: s = "R' F R' B2 R F' R' B2 R2"
        case .edgeCycle: s = "R U' R U R U R U' R' U' R2"
        }
        return CubeMove.parse(s)!
    }
}
