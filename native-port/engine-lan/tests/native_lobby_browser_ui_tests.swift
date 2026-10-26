import XCTest
/// Real browser UI backed by bounded, canned responses in the isolated preview.
final class LobbyBrowserUITests: XCTestCase {
    func testOnlineAndExplicitFavorites() {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .landscapeLeft
        let app = XCUIApplication(); app.launchArguments = ["--lobby-ui-tests"]; app.launch()
        XCTAssertTrue(app.buttons["home.friends"].waitForExistence(timeout: 15))
        app.buttons["home.friends"].tap()
        app.buttons["friends.browse"].tap()
        XCTAssertTrue(app.staticTexts["LIVE-PREVIEW"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["OTHER-ROOM"].exists)
        XCTAssertFalse(app.staticTexts["STALE-HISTORY"].exists)
        XCTAssertFalse(app.staticTexts["OFFLINE-FAVORITE"].exists)
        app.buttons["Add LIVE-PREVIEW to Favorites"].tap()
        app.buttons["♥ Favorites"].tap()
        XCTAssertTrue(app.staticTexts["LIVE-PREVIEW"].exists)
        XCTAssertTrue(app.staticTexts["OFFLINE-FAVORITE"].exists)
        XCTAssertFalse(app.staticTexts["OTHER-ROOM"].exists)
        let image = XCTAttachment(screenshot: app.screenshot()); image.name = "Live and offline explicit favorites"; image.lifetime = .keepAlways; add(image)
        app.buttons["Remove LIVE-PREVIEW from Favorites"].tap()
        XCTAssertFalse(app.staticTexts["LIVE-PREVIEW"].exists)
        app.staticTexts["OFFLINE-FAVORITE"].tap()
        XCTAssertTrue(app.alerts["Multiplayer"].waitForExistence(timeout: 5))
        app.alerts.buttons["OK"].tap()
        XCTAssertTrue(app.staticTexts["OFFLINE-FAVORITE"].exists)
        app.buttons["Online"].tap()
        XCTAssertTrue(app.staticTexts["LIVE-PREVIEW"].exists)
        XCTAssertFalse(app.staticTexts["OFFLINE-FAVORITE"].exists)
        let online = XCTAttachment(screenshot: app.screenshot()); online.name = "Verified online advertisements only"; online.lifetime = .keepAlways; add(online)
    }
}
