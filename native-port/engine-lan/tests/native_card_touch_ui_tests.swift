// Real Simulator coordinate taps against the production HomeView in the
// isolated preview app. No game, download, profile or transport is started.
import XCTest
final class CardTouchUITests: XCTestCase {
    private let points: [(String, CGFloat, CGFloat)] = [
        ("top-left", 0.05, 0.05), ("center", 0.5, 0.5),
        ("title/subtitle", 0.25, 0.82), ("arrow", 0.88, 0.65),
        ("right-edge", 0.97, 0.5), ("bottom", 0.5, 0.97),
        ("lower-left", 0.05, 0.95)
    ]
    override func setUpWithError() throws {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .landscapeLeft
    }
    private func checkCard(_ id: String, page: String) {
        let app = XCUIApplication()
        app.launchArguments = ["--tap-ui-tests"]
        app.launch()
        for (region, x, y) in points {
            XCTContext.runActivity(named: "\(id) · \(region)") { _ in
                let card = app.buttons[id]
                XCTAssertTrue(card.waitForExistence(timeout: 15), "Home card must exist")
                card.coordinate(withNormalizedOffset: CGVector(dx: x, dy: y)).tap()
                XCTAssertTrue(app.staticTexts[page].waitForExistence(timeout: 5), "Tap \(region) must open \(page)")
                if page == "With friends" { XCTAssertFalse(app.buttons["Connection"].exists); XCTAssertTrue(app.buttons["friends.play"].exists) }
                let back = app.buttons["Back"]
                XCTAssertTrue(back.exists); back.tap()
                XCTAssertTrue(card.waitForExistence(timeout: 5), "Back returns to Home")
            }
        }
        let image = XCTAttachment(screenshot: app.screenshot()); image.name = "Home after all card-region taps"; image.lifetime = .keepAlways; add(image)
    }
    func testOnMyOwnEntireCard() { checkCard("home.solo", page: "On my own") }
    func testWithFriendsEntireCard() { checkCard("home.friends", page: "With friends") }
}
