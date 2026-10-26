import CoreGraphics

/// Small template pictograms for vehicle types absent from older SF Symbols.
/// Coordinates use a 32-point square, with the same rounded stroke throughout.
enum VehicleCategoryArtwork {
    static let names: Set<String> = ["helicopter", "motorcycle", "van", "truck", "trailer", "industrial", "boat", "offroad", "racing", "beacon"]

    static func draw(_ name: String, in context: CGContext) {
        context.saveGState()
        defer { context.restoreGState() }
        context.setLineWidth(1.8)
        context.setLineCap(.round)
        context.setLineJoin(.round)
        func line(_ points: [(CGFloat, CGFloat)], close: Bool = false) {
            guard let first = points.first else { return }
            context.beginPath()
            context.move(to: CGPoint(x: first.0, y: first.1))
            for point in points.dropFirst() { context.addLine(to: CGPoint(x: point.0, y: point.1)) }
            if close { context.closePath() }
            context.strokePath()
        }
        func wheel(_ x: CGFloat, _ y: CGFloat, _ radius: CGFloat = 3) {
            context.strokeEllipse(in: CGRect(x: x-radius, y: y-radius, width: 2*radius, height: 2*radius))
        }
        switch name {
        case "helicopter":
            line([(4, 5), (28, 5)]); line([(16, 5), (16, 11)])
            line([(10, 12), (20, 12), (27, 17), (29, 20), (25, 23), (11, 23), (7, 19)], close: true)
            line([(20, 12), (19, 18), (27, 18)])
            line([(8, 16), (2, 13), (2, 19), (9, 20)]); line([(2, 10), (2, 13)])
            line([(12, 23), (11, 27)]); line([(23, 23), (24, 27)])
            line([(7, 27), (27, 27), (29, 25)])
        case "motorcycle":
            wheel(7, 24, 4); wheel(25, 24, 4)
            line([(7, 24), (12, 16), (19, 16), (25, 24)])
            line([(12, 16), (17, 24), (7, 24)]); line([(17, 24), (22, 18)])
            line([(25, 24), (21, 10), (17, 10)]); line([(6, 14), (12, 14)])
        case "van":
            line([(3, 23), (3, 10), (20, 10), (28, 17), (29, 23), (27, 23)])
            line([(5, 23), (3, 23)]); line([(11, 23), (21, 23)])
            line([(18, 10), (18, 18), (27, 18)]); line([(8, 13), (14, 13), (14, 18), (8, 18)], close: true)
            wheel(8, 24); wheel(24, 24)
        case "truck":
            line([(3, 21), (3, 8), (19, 8), (19, 22), (11, 22)])
            line([(19, 13), (25, 13), (29, 19), (29, 23), (27, 23)])
            line([(22, 14), (22, 19), (28, 19)]); line([(12, 23), (21, 23)])
            wheel(8, 24); wheel(24, 24)
        case "trailer":
            line([(2, 8), (25, 8), (25, 22), (2, 22)], close: true)
            line([(25, 20), (30, 23)]); line([(4, 11), (4, 18)])
            wheel(8, 25); wheel(17, 25)
        case "industrial":
            line([(3, 20), (3, 16), (11, 16), (11, 10), (19, 10), (22, 20)], close: true)
            line([(14, 10), (14, 16), (20, 16)])
            line([(22, 18), (27, 18), (27, 23), (30, 23), (30, 16)])
            context.stroke(CGRect(x: 3, y: 23, width: 20, height: 5))
        case "boat":
            line([(2, 20), (29, 20), (25, 26), (8, 26)], close: true)
            line([(9, 20), (12, 14), (22, 14), (25, 20)])
            line([(16, 14), (16, 9), (22, 9)])
            line([(3, 29), (7, 28), (11, 29), (15, 28), (19, 29), (23, 28), (28, 29)])
        case "offroad":
            line([(3, 20), (5, 14), (11, 14), (13, 9), (22, 9), (26, 16), (29, 18), (29, 23), (28, 23)])
            line([(4, 23), (3, 23), (3, 20)]); line([(12, 23), (20, 23)])
            line([(14, 10), (14, 16), (25, 16)]); wheel(8, 24, 4); wheel(24, 24, 4)
        case "racing":
            line([(2, 21), (10, 21), (15, 16), (20, 16), (22, 21), (30, 21)])
            line([(6, 17), (6, 26)]); line([(26, 17), (26, 26)])
            line([(3, 27), (29, 27)]); line([(11, 9), (23, 9)]); line([(17, 9), (17, 14)])
            context.stroke(CGRect(x: 3, y: 20, width: 5, height: 6))
            context.stroke(CGRect(x: 24, y: 20, width: 5, height: 6))
        case "beacon":
            line([(7, 25), (9, 15), (13, 11), (19, 11), (23, 15), (25, 25)], close: true)
            line([(5, 28), (27, 28)]); line([(16, 3), (16, 6)])
            line([(4, 7), (7, 10)]); line([(25, 10), (28, 7)])
            line([(2, 17), (5, 17)]); line([(27, 17), (30, 17)])
        default: break
        }
    }
}
