import Foundation
import UIKit

/// Sends the app's logs to the developer (5★ Port Builder site, which forwards them on Telegram).
enum LogUploader {
    static let endpoint = URL(string: "https://fivestarport.vercel.app/api/log")!
    /// The site accepts up to 4 MB, so each log is trimmed to its last 1.8 MB.
    private static let perLog = 1_800_000

    static func send(note: String, done: @escaping ((String, String)) -> Void) {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        var body = Data()
        for (title, name) in [("PREVIOUS RUN", "native-port-previous.log"), ("THIS RUN", "native-port.log")] {
            guard let data = try? Data(contentsOf: documents.appendingPathComponent(name)), !data.isEmpty else { continue }
            body.append("===== \(title) (\(name)) =====\n".data(using: .utf8)!)
            body.append(data.count > perLog ? data.suffix(perLog) : data)
            body.append("\n".data(using: .utf8)!)
        }
        guard !body.isEmpty else { DispatchQueue.main.async { done((L10n.text("No log yet"), L10n.text("Start the game once, then try again."))) }; return }
        var request = URLRequest(url: endpoint, timeoutInterval: 60)
        request.httpMethod = "POST"
        request.setValue("text/plain; charset=utf-8", forHTTPHeaderField: "Content-Type")
        request.setValue("\(GameSettings.shared.tier.model) · iOS \(UIDevice.current.systemVersion) · \(GameSettings.shared.tier.physicalMemoryMB) MB device RAM", forHTTPHeaderField: "X-Device")
        request.setValue(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?", forHTTPHeaderField: "X-App-Version")
        request.setValue(String(note.prefix(400)).addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? "", forHTTPHeaderField: "X-Note")
        URLSession.shared.uploadTask(with: request, from: body) { data, response, error in
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let reply = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let result: (String, String)
            if status == 200 {
                result = ("Log sent, thank you!", "Reference: \(reply?["id"] as? String ?? "-"). Mention it if you also ask for help in the community.")
            } else if error != nil {
                result = ("Couldn't send the log", "No internet connection? Try again, or use Share log instead.")
            } else {
                result = ("Couldn't send the log", (reply?["error"] as? String) ?? "Try again later, or use Share log instead.")
            }
            DispatchQueue.main.async { done(result) }
        }.resume()
    }
}

/// "Send log to the developer": its own screen so the buttons stay visible above the keyboard in landscape.
final class SendLogViewController: UIViewController {
    private let note = UITextView()
    private let status = UILabel()
    var finished: ((String, String) -> Void)?

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Send log to the developer"
        view.backgroundColor = .systemGroupedBackground
        navigationItem.leftBarButtonItem = UIBarButtonItem(systemItem: .cancel, primaryAction: UIAction { [weak self] _ in self?.dismiss(animated: true) })
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Send", primaryAction: UIAction { [weak self] _ in self?.send() })
        navigationItem.rightBarButtonItem?.style = .done

        let info = UILabel()
        info.text = "Sends this run's game log and the previous one: your iPhone model, iOS version, app settings and what the game printed. No personal data, photos or contacts."
        info.numberOfLines = 0
        info.font = .preferredFont(forTextStyle: .footnote)
        info.textColor = .secondaryLabel
        note.font = .preferredFont(forTextStyle: .body)
        note.layer.cornerRadius = 10
        note.backgroundColor = .secondarySystemGroupedBackground
        note.textContainerInset = UIEdgeInsets(top: 10, left: 8, bottom: 10, right: 8)
        note.accessibilityLabel = "What happened? (optional)"
        let placeholder = UILabel()
        placeholder.text = "What happened? (optional)"
        placeholder.textColor = .placeholderText
        placeholder.font = note.font
        placeholder.tag = 7
        note.addSubview(placeholder)
        placeholder.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([placeholder.topAnchor.constraint(equalTo: note.topAnchor, constant: 10),
                                     placeholder.leadingAnchor.constraint(equalTo: note.leadingAnchor, constant: 13)])
        NotificationCenter.default.addObserver(forName: UITextView.textDidChangeNotification, object: note, queue: .main) { [weak self] _ in
            self?.note.viewWithTag(7)?.isHidden = !(self?.note.text.isEmpty ?? true)
        }
        status.font = .preferredFont(forTextStyle: .footnote)
        status.textColor = .secondaryLabel
        let stack = UIStackView(arrangedSubviews: [info, note, status])
        stack.axis = .vertical
        stack.spacing = 10
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 16),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -16),
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            // The note shrinks to stay above the keyboard.
            stack.bottomAnchor.constraint(lessThanOrEqualTo: view.keyboardLayoutGuide.topAnchor, constant: -8),
            note.heightAnchor.constraint(greaterThanOrEqualToConstant: 44),
        ])
        let preferred = note.heightAnchor.constraint(equalToConstant: 140)
        preferred.priority = .defaultLow
        preferred.isActive = true
    }

    private func send() {
        navigationItem.rightBarButtonItem?.isEnabled = false
        note.resignFirstResponder()
        status.text = "Sending…"
        LogUploader.send(note: note.text ?? "") { [weak self] result in
            guard let self else { return }
            let done = self.finished
            self.dismiss(animated: true) { done?(result.0, result.1) }
        }
    }
}
