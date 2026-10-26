import UIKit
import WebKit

/// A small browser for download pages ("click Download to start"): the player uses the page as
/// normal, and as soon as it starts sending a file, the app takes the download over and unpacks
/// it as it arrives (with the page's cookies, so sessions and download tokens still work).
final class DownloadBrowserViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    /// The file the page started sending, with the headers needed to fetch it the same way.
    var onDownload: ((URL, [String: String]) -> Void)?
    private let start: URL
    private var webView: WKWebView!
    private let hint = UILabel()
    private let progress = UIProgressView(progressViewStyle: .bar)
    private var observation: NSKeyValueObservation?
    private var caught = false
    /// The same browser identity is used for the page and for the app's download.
    private static let userAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    private static let archiveTypes: Set<String> = ["application/zip", "application/x-zip-compressed", "application/x-zip", "application/vnd.rar",
                                                    "application/x-rar-compressed", "application/x-rar", "application/x-7z-compressed",
                                                    "application/octet-stream", "application/x-tar", "binary/octet-stream"]

    init(url: URL) {
        start = url
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = start.host
        view.backgroundColor = Theme.night
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
        // Pages may not open new windows by script: ad pop-ups go nowhere, file links still load here.
        configuration.userContentController.addUserScript(WKUserScript(source: Self.popupGuard, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        webView = WKWebView(frame: .zero, configuration: configuration)
        // The page loads once the ad blocking is in place.
        Self.adRules { [weak self] rules in
            guard let self else { return }
            if let rules { self.webView.configuration.userContentController.add(rules) }
            self.webView.load(URLRequest(url: self.start))
        }
        webView.customUserAgent = Self.userAgent
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        hint.text = "Tap the page's download button. The app takes the download over by itself and unpacks it."
        hint.font = Theme.body(13, .medium)
        hint.textColor = Theme.text
        hint.numberOfLines = 2
        hint.textAlignment = .center
        hint.backgroundColor = Theme.accentDeep.withAlphaComponent(0.9)
        progress.progressTintColor = Theme.accent
        for item in [webView!, hint, progress] as [UIView] { item.translatesAutoresizingMaskIntoConstraints = false; view.addSubview(item) }
        let guide = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            hint.topAnchor.constraint(equalTo: guide.topAnchor),
            hint.leadingAnchor.constraint(equalTo: view.leadingAnchor), hint.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            hint.heightAnchor.constraint(greaterThanOrEqualToConstant: 34),
            progress.topAnchor.constraint(equalTo: hint.bottomAnchor),
            progress.leadingAnchor.constraint(equalTo: view.leadingAnchor), progress.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.topAnchor.constraint(equalTo: progress.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor), webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        navigationItem.leftBarButtonItem = UIBarButtonItem(systemItem: .close, primaryAction: UIAction { [weak self] _ in self?.dismiss(animated: true) })
        navigationItem.rightBarButtonItems = [
            UIBarButtonItem(image: UIImage(systemName: "arrow.clockwise"), primaryAction: UIAction { [weak self] _ in self?.webView.reload() }),
            UIBarButtonItem(image: UIImage(systemName: "chevron.backward"), primaryAction: UIAction { [weak self] _ in self?.webView.goBack() })
        ]
        observation = webView.observe(\.estimatedProgress) { [weak self] web, _ in
            self?.progress.setProgress(Float(web.estimatedProgress), animated: true)
            self?.progress.isHidden = web.estimatedProgress >= 1
        }
    }

    // MARK: Catching the download

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        // Clicks hijacked to an ad network go nowhere.
        if Self.isAd(navigationAction.request.url) {
            GameFolder.log("Browser blocked a redirect to \(navigationAction.request.url?.host ?? "?")")
            decisionHandler(.cancel); return
        }
        // Links with a download attribute go straight to a download.
        decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let response = navigationResponse.response
        let disposition = (response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")?.lowercased() ?? ""
        let type = response.mimeType?.lowercased() ?? ""
        let big = response.expectedContentLength > 50_000_000
        if disposition.contains("attachment") || Self.archiveTypes.contains(type) || big || !navigationResponse.canShowMIMEType,
           let url = response.url {
            decisionHandler(.cancel)
            take(url)
        } else {
            decisionHandler(.allow)
        }
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { catchDownload(download) }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { catchDownload(download) }
    private func catchDownload(_ download: WKDownload) {
        download.delegate = self
        let url = download.originalRequest?.url
        download.cancel { _ in }
        if let url { take(url) }
    }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        completionHandler(nil) // cancelled: the app downloads it itself
    }

    /// New windows: only a link that looks like the file itself is followed (here); everything else,
    /// which on download portals is nearly always an ad, is dropped.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, Self.looksLikeFile(url) { webView.load(navigationAction.request) }
        else { GameFolder.log("Browser blocked a pop-up: \(navigationAction.request.url?.host ?? "?")") }
        return nil
    }

    private static func looksLikeFile(_ url: URL) -> Bool {
        let name = url.lastPathComponent.lowercased()
        return [".zip", ".rar", ".7z", ".001"].contains(where: name.hasSuffix) || name.range(of: #"\.(z|r)\d\d$"#, options: .regularExpression) != nil
            || url.path.lowercased().contains("download")
    }

    /// Replaces window.open: file links open in this page, anything else is ignored.
    private static let popupGuard = """
    (function(){
      var looksLikeFile=function(u){try{var p=new URL(u,location.href).pathname.toLowerCase();return /\\.(zip|rar|7z|001)$|\\.(z|r)\\d\\d$|download/.test(p);}catch(e){return false;}};
      window.open=function(u){ if(u&&looksLikeFile(u)){ location.href=u; } return null; };
    })();
    """

    /// Content blocking for the ad and pop-under networks download portals use (compiled once).
    private static var compiledRules: WKContentRuleList?
    private static func adRules(_ done: @escaping (WKContentRuleList?) -> Void) {
        if let compiledRules { done(compiledRules); return }
        let rules = adNetworks.map { domain in
            ["trigger": ["url-filter": NSRegularExpression.escapedPattern(for: domain), "url-filter-is-case-sensitive": false], "action": ["type": "block"]] as [String: Any]
        }
        guard let data = try? JSONSerialization.data(withJSONObject: rules), let json = String(data: data, encoding: .utf8) else { done(nil); return }
        WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "download-portal-ads-v2", encodedContentRuleList: json) { list, error in
            if let error { GameFolder.log("Browser ad rules didn't compile: \(error.localizedDescription)") }
            compiledRules = list
            done(list)
        }
    }

    /// The ad and pop-under networks download portals use.
    private static let adNetworks = ["propellerads.com", "propellerclick.com", "popads.net", "popcash.net", "adsterra.com", "adsterratools.com",
                        "exoclick.com", "exosrv.com", "juicyads.com", "a-ads.com", "adcash.com", "hilltopads.net", "hilltopads.com",
                        "clickadu.com", "monetag.com", "onclickads.net", "onclickalgo.com", "onclckmn.com", "popmyads.com", "trafficjunky.net",
                        "ad-maven.com", "admaven.com", "adspyglass.com", "pushame.com", "richpush.co", "evadav.com", "galaksion.com",
                        "realsrv.com", "highperformanceformat.com", "profitablecpmrate.com", "effectiveratecpm.com", "displayvertising.com",
                        "doubleclick.net", "googlesyndication.com", "adservice.google.com", "taboola.com", "outbrain.com", "mgid.com",
                        "revcontent.com", "zeropark.com", "trafficstars.com", "tsyndicate.com", "adnium.com", "clickaine.com", "pemsrv.com",
                        "bidgear.com", "yllix.com", "ylx-1.com", "ylx-2.com", "ad.plus", "adskeeper.com", "adskeeper.co.uk", "acint.net",
                        "s.pemsrv.com", "betterads.co", "notifpush.com", "pushprofit.net", "go.oclasrv.com", "oclasrv.com", "onclasrv.com"]
    private static func isAd(_ url: URL?) -> Bool {
        guard let host = url?.host?.lowercased() else { return false }
        return adNetworks.contains { host == $0 || host.hasSuffix("." + $0) }
    }

    /// Hands the file to the app with the page's cookies, so the server treats it as the same visit.
    private func take(_ url: URL) {
        guard !caught else { return }
        caught = true
        hint.text = "Download caught. Starting…"
        let referer = webView.url?.absoluteString
        webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { [weak self] cookies in
            guard let self else { return }
            let host = url.host ?? ""
            let matching = cookies.filter { cookie in
                let domain = cookie.domain.hasPrefix(".") ? String(cookie.domain.dropFirst()) : cookie.domain
                return host == domain || host.hasSuffix("." + domain)
            }
            var headers = ["User-Agent": Self.userAgent]
            if !matching.isEmpty { headers["Cookie"] = matching.map { "\($0.name)=\($0.value)" }.joined(separator: "; ") }
            if let referer { headers["Referer"] = referer }
            GameFolder.log("Browser caught a download from \(host) (\(matching.count) cookies)")
            self.dismiss(animated: true) { self.onDownload?(url, headers) }
        }
    }
}
