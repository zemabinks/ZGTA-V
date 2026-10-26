import Foundation
import CoreGraphics

@main
struct TestCamera {
    static func main() {
        let first = NSObject(), second = NSObject()
        let a = ObjectIdentifier(first), b = ObjectIdentifier(second)
        var camera = DragCamera()
        camera.begin(a, at: .zero)
        camera.move(a, to: CGPoint(x: 1, y: 1))
        assert(camera.velocity(elapsed: 1.0/60, sensitivity: 1, aimed: true) == .zero)
        camera.move(a, to: CGPoint(x: 5, y: 1))
        let move = camera.velocity(elapsed: 1.0/60, sensitivity: 1, aimed: true)
        assert(move.x == 240 && move.y == 0)
        assert(camera.velocity(elapsed: 1.0/60, sensitivity: 1, aimed: true) == .zero, "Holding must not keep rotating")
        camera.begin(b, at: CGPoint(x: 300, y: 300))
        camera.move(b, to: CGPoint(x: 305, y: 300))
        camera.end(a)
        assert(camera.velocity(elapsed: 1.0/60, sensitivity: 1, aimed: true).x == 300, "One finger must not reset another")
        camera.move(b, to: CGPoint(x: 310, y: 300))
        assert(camera.velocity(elapsed: 0.5, sensitivity: 1, aimed: true) == .zero, "Discard suspended input")
        camera.move(b, to: CGPoint(x: 315, y: 300)); camera.reset()
        assert(camera.velocity(elapsed: 1.0/60, sensitivity: 1, aimed: true) == .zero)
        func drag(hz: Double) -> CGFloat {
            var c = DragCamera(); c.begin(a, at: .zero)
            var total: CGFloat = 0
            for i in 1...Int(hz) {
                c.move(a, to: CGPoint(x: Double(i)*120/hz, y: 0))
                total += c.velocity(elapsed: 1/hz, sensitivity: 1, aimed: true).x / hz
            }
            return total
        }
        assert(abs(drag(hz: 30)-drag(hz: 60)) <= 2)
        assert(abs(drag(hz: 60)-drag(hz: 120)) <= 2)
        // Free-look and aim use the same screen-coordinate Y direction.
        for sensitivity in [1.0, 4.0, 10.0] {
            for inverted in [false, true] {
                for direction in [-1.0, 1.0] {
                    var c = DragCamera(); c.begin(a, at: .zero)
                    c.move(a, to: CGPoint(x: 10, y: 10 * direction))
                    let delta = c.motion(sensitivity: sensitivity, invertedY: inverted)
                    assert(delta.x == 10 * sensitivity)
                    assert(abs(delta.y - 8.5 * direction * sensitivity * (inverted ? -1 : 1)) < 0.00001)
                    assert(c.motion(sensitivity: sensitivity, invertedY: inverted) == .zero, "Consume each drag only once")
                }
            }
        }
        print("Camera: idle, independent fingers, suspend, reset and 30/60/120 Hz passed")
    }
}
