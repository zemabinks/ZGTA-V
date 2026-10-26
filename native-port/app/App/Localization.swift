import Foundation

enum L10n {
    static let language = "en"
    // The app is English only, including upgrades with an older language preference.
    // Leave unrelated saved preferences and player data untouched.
    static func preferredLanguage(in defaults: UserDefaults) -> String {
        "en"
    }
    static let translations: [String: [String: String]] = {
        guard let url = Bundle.main.url(forResource: "Localizations", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let values = try? JSONDecoder().decode([String: [String: String]].self, from: data) else { return [:] }
        return values
    }()
    static func text(_ source: String) -> String {
        text(source, language: language, catalog: translations)
    }
    static func text(_ source: String, language: String, catalog: [String: [String: String]]) -> String {
        // Only exact legacy role identifiers need presentation aliases. Never
        // rewrite substrings in filenames, player names or formatted messages.
        catalog[source]?["en"] ?? source
    }
}
