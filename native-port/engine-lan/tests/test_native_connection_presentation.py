"""Drive the actual native connection UI offline through alert actions.

Only UIKit presentation, profile persistence, backend readiness and the session
transport boundary are doubled. Production status handling, success/failure presentation, queued Play,
field validation and action enablement are compiled
unmodified. No sockets, app data, device, game instance or listener is used.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

DOUBLES=r'''
import Foundation
var sessionRestartRequests = 0
func ZemaLabEnabled() -> Int32 { 1 }
func PGRequestSessionRestart() -> Bool { sessionRestartRequests += 1; return true }
func PGSessionRestartStatus() -> Int32 { 4 }
final class MemoryPreferences: EngineLanPreferenceStore {
    var values: [String: Any] = [:]
    func string(forKey key: String) -> String? { values[key] as? String }
    func set(_ value: Any?, forKey key: String) { values[key]=value }
}
let testPreferences = MemoryPreferences()

final class UIApplication {
    static let shared = UIApplication()
    static let didEnterBackgroundNotification = Notification.Name("fixture-background")
    static let willTerminateNotification = Notification.Name("fixture-terminate")
    var isIdleTimerDisabled = false
}
final class UIPasteboard { static let general = UIPasteboard(); var string: String? }
struct PhoneRelayAddresses {
    var lan: String? = "192.168.1.9"
    var vpn: String? = "100.70.1.9"
    static var available = PhoneRelayAddresses()
    static func current() -> PhoneRelayAddresses { available }
}
final class PhoneRelayServer {
    struct Snapshot { let online: Int; let running: Bool; let message: String }
    static var latest: PhoneRelayServer!
    var changed: ((Snapshot) -> Void)?
    var diagnostic: ((String) -> Void)?
    var completion: ((Result<Void,Error>) -> Void)?
    var addresses: [String] = []
    var room = ""
    var stopped = false
    init() { Self.latest = self }
    func start(addresses: [String], room: String, completion: @escaping (Result<Void,Error>) -> Void) {
        self.addresses=addresses; self.room=room; self.completion=completion
    }
    func stop() { stopped=true }
    func ready() { changed?(Snapshot(online:0,running:true,message:"Ready"));completion?(.success(())) }
    func fail() { completion?(.failure(NSError(domain:"fixture",code:49,userInfo:[NSLocalizedDescriptionKey:"Listener failed at 127.0.0.1:47540: POSIX 49"]))) }
}
class UIViewController: NSObject {
    var presentedViewController: UIViewController?
    func present(_ controller: UIViewController, animated: Bool) {
        precondition(presentedViewController == nil, "Presentation must not stack panels")
        presentedViewController = controller
    }
}
final class UITextField {
    enum Capitalization { case none, allCharacters }
    enum Correction { case no }
    var text: String?
    var placeholder: String?
    var autocapitalizationType: Capitalization = .none
    var autocorrectionType: Correction = .no
}
final class UIAlertAction {
    enum Style { case `default`, cancel, destructive }
    let title: String?
    let style: Style
    var isEnabled = true
    private let handler: ((UIAlertAction) -> Void)?
    init(title: String?, style: Style, handler: ((UIAlertAction) -> Void)? = nil) {
        self.title=title;self.style=style;self.handler=handler
    }
    func tap(from controller: UIViewController) {
        guard isEnabled else { return }
        // UIKit dismisses its alert when an action is selected.
        let panel=controller.presentedViewController
        controller.presentedViewController=nil
        withExtendedLifetime(panel) { handler?(self) }
    }
}
final class UIAlertController: UIViewController {
    enum Style { case alert }
    let title: String?
    var message: String?
    var textFields: [UITextField]? = []
    private(set) var actions: [UIAlertAction] = []
    init(title: String?, message: String?, preferredStyle: Style) {
        self.title=title;self.message=message;super.init()
    }
    func addAction(_ action: UIAlertAction) { actions.append(action) }
    func addTextField(configurationHandler: ((UITextField) -> Void)?) {
        let field=UITextField();configurationHandler?(field);textFields!.append(field)
    }
}

private var transport: Int32 = 0
private var prepared: Int32 = 0
private var profileConfigureCount = 0
private var profileLoadCount = 0
private var profileCommitCount = 0
private var profileDisplayName = "zema"
private var profileAdmitted = false
func ZemaLanTransportReady() -> Int32 { transport }
func ZemaLanGameReady() -> Int32 { transport == 1 && prepared == 1 ? 1 : 0 }
func ZemaLanPrepared(_ value: Int32) { prepared=value }
func ZemaProfileReady() -> Int32 { 1 }
func ZemaProfileRevision() -> UInt64 { 0 }
func ZemaProfileConfigure(_ id: UInt32, _ bytes: UnsafePointer<UInt8>?, _ count: Int) -> Int32 { profileConfigureCount+=1;return 1 }
func ZemaProfileName(_ bytes: UnsafeMutablePointer<UInt8>?, _ capacity: Int) -> Int {
    let name=Array(profileDisplayName.utf8);precondition(capacity>name.count)
    for (index,byte) in name.enumerated() { bytes![index]=byte }
    bytes![name.count]=0;return name.count
}
final class EngineLanProfileFile {
    enum Failure: Error { case unavailable, renameLocked;var message: String { "Profile unavailable or name locked." } }
    static func profileDirectory(inAppDocuments documents: URL) throws -> URL { documents }
    init(directory: URL) throws {}
    func load() throws -> Bool { profileLoadCount+=1;return true }
    func commit() throws { profileCommitCount+=1 }
    func rename(to name: String) throws {
        if name == profileDisplayName { return }
        guard !profileAdmitted else { throw Failure.renameLocked }
        if CommandLine.arguments[1] == "rename-failure" { throw Failure.unavailable }
        profileDisplayName=name;profileCommitCount+=1
    }
}
final class EngineLanSession {
    struct Backend { static let native = Backend() }
    static var latest: EngineLanSession!
    private(set) var connectCount=0
    private(set) var admittedNames: [String] = []
    var status: ((String) -> Void)?
    init(backend: Backend) { Self.latest=self }
    static func validEndpoint(_ text: String) -> URL? { URL(string:text) }
    func connect(endpoint: String, room: String, name: String) {
        precondition(endpoint.hasPrefix("ws://") && !room.isEmpty && !name.isEmpty)
        connectCount+=1
        admittedNames.append(name)
    }
    func disconnect() { transport=0 }
    func result(_ message: String, admitted: Bool = false) {
        transport=admitted ? 1 : 0
        if admitted { profileAdmitted=true }
        status?(message)
    }
}
'''

HARNESS=r'''
func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fputs("FAIL: \(message)\n",stderr);exit(3) }
}
func spin(_ seconds: TimeInterval) {
    let end=Date().addingTimeInterval(seconds)
    while Date()<end { RunLoop.main.run(until:Date().addingTimeInterval(0.005)) }
}
func alert(_ controller: UIViewController) -> UIAlertController {
    guard let result=controller.presentedViewController as? UIAlertController else {
        fputs("FAIL: no presented connection panel\n",stderr);exit(3)
    }
    return result
}
func action(_ panel: UIAlertController, _ title: String) -> UIAlertAction {
    guard let result=panel.actions.first(where:{$0.title==title}) else {
        fputs("FAIL: missing action \(title)\n",stderr);exit(3)
    }
    return result
}
@main struct ConnectionPresentation {
    static func main() {
        if CommandLine.arguments[1] != "saved-empty" && !CommandLine.arguments[1].hasPrefix("host-") && !CommandLine.arguments[1].hasPrefix("remote-") { testPreferences.set("ws://192.168.1.33:47540/engine-lan", forKey:EngineLanPreferences.relayKey) }
        let ui=ZemaEngineLANUI.shared,controller=UIViewController()
        let scenario=CommandLine.arguments[1]
        if scenario == "saved-ready" || scenario == "saved-empty" {
            if scenario == "saved-empty" { testPreferences.values.removeAll() }
            // Preferences are read when the singleton is initialized above; clear
            // uses a process with no setup through the initialization guard below.
            var plays=0
            let handled=ui.playConfigured(from:controller,play:{plays+=1})
            if scenario == "saved-empty" {
                check(!handled && controller.presentedViewController==nil && plays==0,"First Play remains at Home without a duplicate role chooser")
            } else {
                check(handled && controller.presentedViewController==nil && plays==0,"Saved Play waits without showing setup")
                check(ui.playConfigured(from:controller,play:{plays+=1}),"Repeated Play while connecting is handled")
                EngineLanSession.latest!.result("Connected",admitted:true);spin(0.5)
                check(plays==1,"Saved Play starts once after successful admission")
            }
            print("SAVED_PLAY_PASS");print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM");return
        }
        if scenario == "choose-host" || scenario == "browse-final" {
            var plays=0
            if scenario == "choose-host" {
                ui.presentSetup(from:controller,role:"choose",selected:{})
                check(alert(controller).actions.map{$0.title!} == ["Join a friend","Create a lobby","Cancel"],"Merged card offers both roles")
                action(alert(controller),"Create a lobby").tap(from:controller);spin(0.35)
                check(ui.selectedRole=="host" && plays==0,"Choosing Host configures the button, never launches")
                action(alert(controller),"LAN").tap(from:controller);spin(0.35)
                action(alert(controller),"Create lobby").tap(from:controller)
                PhoneRelayServer.latest.ready();EngineLanSession.latest.result("Connected",admitted:true);spin(0.5)
                check(ui.ready && plays==0 && controller.presentedViewController==nil,"Ready host waits for green Host multiplayer")
                check(ui.playConfigured(from:controller,play:{plays+=1}) && plays==1,"Explicit final Host enters game once")
                // Rejected Join / Browse cannot relabel an admitted host as a guest.
                ui.presentSetup(from:controller,role:"browse",selected:{});spin(0.35)
                check(ui.selectedRole=="host" && ui.ready,"Rejected browse preserves actual host role and connection")
            } else {
                ui.presentSetup(from:controller,role:"browse",selected:{})
                check(ui.selectedRole=="browse" && plays==0,"Browsing is setup only")
                LobbyBrowserPresenter.selection?(LobbyRecord(relay:"ws://192.168.1.9:47540/engine-lan",room:"FOUND"));spin(0.35)
                action(alert(controller),"Connect").tap(from:controller)
                EngineLanSession.latest.result("Connected",admitted:true);spin(0.5)
                check(ui.ready && plays==0 && controller.presentedViewController==nil,"Found lobby admission waits for final green action")
                check(ui.playConfigured(from:controller,play:{plays+=1}) && plays==1,"Final Play launches browsed session once")
            }
            print("FINAL_GREEN_GATE_PASS");print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM");return
        }
        if scenario.hasPrefix("quick-") {
            let session=EngineLanSession.latest!
            if scenario == "quick-join" || scenario == "quick-invite" {
            var plays=0; var selected=0
            ui.presentSetup(from:controller,role:"join",selected:{selected+=1})
            action(alert(controller),"LAN").tap(from:controller);spin(0.35)
            let panel=alert(controller)
            panel.textFields?[0].text=scenario == "quick-invite" ? "zgtav://join?relay=ws%3A%2F%2F100.70.1.9%3A47541%2Fengine-lan&room=ROOM+%2B+north" : "192.168.1.9:47541"
            panel.textFields?[1].text="LOS-SANTOS"
            action(panel,"Connect").tap(from:controller)
            check(plays==0 && selected==2,"Explicit join selects multiplayer but waits for admission")
            if scenario == "quick-invite" { check(testPreferences.string(forKey:EngineLanPreferences.connectionKey)=="Remote" && testPreferences.string(forKey:EngineLanPreferences.remoteRoomKey)=="ROOM + north","Invite selects its network and room") }
            session.result("Connected",admitted:true);spin(0.5)
            check(plays==0 && ui.ready && controller.presentedViewController==nil,"Successful setup returns ready without launching")
            session.result("Connected",admitted:true);spin(0.5)
            check(plays==0,"Repeated readiness cannot launch without the final green action")
            check(ui.playConfigured(from:controller,play:{plays+=1}),"Final green action starts the ready game")
            check(plays==1,"Final green action launches exactly once")
            session.result("Connected",admitted:true);spin(0.5);check(plays==1,"Repeated status must not relaunch")
            print("QUICK_JOIN_PASS")
            } else {
            let plays=0
            ui.presentSetup(from:controller,role:"join",selected:{})
            action(alert(controller),"Cancel").tap(from:controller)
            ui.present(from:controller,running:false)
            let panel=alert(controller);panel.textFields?[0].text="ws://192.168.1.9:47540/engine-lan"
            action(panel,"Connect").tap(from:controller);session.result("Connected",admitted:true);spin(0.5)
            check(plays==0,"Cancel must clear deferred quick launch")
            print("QUICK_CANCEL_PASS")
            }
            print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM");return
        }
        if scenario.hasPrefix("host-") {
            let remote = scenario.contains("remote")
            if scenario == "host-remote-cellular" || scenario == "host-remote-failure" {
                PhoneRelayAddresses.available.lan = nil
            }
            var selected=0
            ui.presentChoices(from:controller) { selected+=1 }
            action(alert(controller),scenario.contains("remote") ? "Remote" : "LAN").tap(from:controller);spin(0.37)
            let roles=alert(controller)
            check(roles.actions.map { $0.title! } == ["Join a game","Create lobby","Cancel"],"LAN must offer hosting and joining")
            action(roles,"Create lobby").tap(from:controller);spin(0.37)
            let setup=alert(controller)
            check(setup.textFields?.count==(remote ? 3 : 2),"Host field count matches role")
            check(setup.message?.contains(remote ? "cellular" : "192.168.1.9")==true,"Host setup explains selected network")
            setup.textFields![remote ? 1 : 0].text="PHONE-ROOM"
            action(setup,"Create lobby").tap(from:controller)
            let host=PhoneRelayServer.latest!
            check(host.addresses == (remote ? ["127.0.0.1","100.70.1.9"] : ["127.0.0.1","192.168.1.9"]),"Bind loopback and selected guest-facing private network")
            check(host.room=="PHONE-ROOM" && EngineLanSession.latest.connectCount==0,"Do not join until listener ready")
            if scenario=="host-failure" || scenario=="host-remote-failure" {
                host.fail();spin(0.37)
                check(!ui.ready && alert(controller).message?.contains("POSIX 49")==true,"Host failure must preserve actual OS error")
                if remote { check(alert(controller).message?.contains("does not require Wi-Fi")==true && alert(controller).message?.contains("check Wi-Fi") != true,"Remote failure does not demand Wi-Fi") }
                check(!UIApplication.shared.isIdleTimerDisabled,"Failed hosting must not hold phone awake")
            } else {
                host.ready()
                check(EngineLanSession.latest.connectCount==1,"Host joins its own relay exactly once")
                check(testPreferences.string(forKey:EngineLanPreferences.relayKey)==nil,"Hosting preserves prior join preferences")
                EngineLanSession.latest.result("Fixture host self admitted",admitted:true);spin(0.47)
                check(ui.ready && controller.presentedViewController==nil,"Host success stays on home, ready to Play")
                check(UIApplication.shared.isIdleTimerDisabled,"Keep active host awake")
                if scenario=="host-background" {
                    NotificationCenter.default.post(name:UIApplication.didEnterBackgroundNotification,object:nil);spin(0.03)
                    check(host.stopped && !ui.ready && !UIApplication.shared.isIdleTimerDisabled,"Background stops host and restores idle state")
                    ui.present(from:controller,running:true)
                    check(alert(controller).message?.contains("left the foreground")==true,"Explain why hosting stopped")
                } else {
                    ui.present(from:controller,running:true)
                    let panel=alert(controller)
                    check(panel.message?.contains("Hosted on this iPhone")==true,"Host address panel")
                    action(panel,"Copy join address").tap(from:controller)
                    check(UIPasteboard.general.string?.contains(remote ? "100.70.1.9" : "192.168.1.9")==true,"Copy correct phone address")
                    ui.present(from:controller,running:true)
                    action(alert(controller),"Stop hosting").tap(from:controller)
                    check(host.stopped && !UIApplication.shared.isIdleTimerDisabled && !ui.ready,"Explicit Stop closes own host and releases idle lock")
                    ui.present(from:controller,running:true)
                    action(alert(controller),"Start hosting again").tap(from:controller);spin(0.37)
                    action(alert(controller),"Create lobby").tap(from:controller)
                    let restarted=PhoneRelayServer.latest!
                    check(restarted !== host && restarted.room=="PHONE-ROOM","Restart creates a new relay with the same room")
                    restarted.ready()
                    check(EngineLanSession.latest.connectCount==2,"Host restarts local transport without starting another engine")
                    EngineLanSession.latest.result("Fixture recovered host",admitted:true);spin(0.47)
                    check(ui.ready && UIApplication.shared.isIdleTimerDisabled,"Restarted host reuses saved character and stays awake")
                }
            }
            check(selected==1 && profileLoadCount==1 && profileConfigureCount==0,"Preserve saved character during hosting")
            print("PHONE_HOST_UI_"+scenario+"_PASS")
            print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM")
            return
        }
        if scenario.hasPrefix("remote-") {
            var choices=0
            ui.presentChoices(from:controller) { choices+=1 }
            let menu=alert(controller)
            check(menu.actions.map { $0.title! } == ["LAN","Remote","Cancel"],"Exactly LAN and Remote choices")
            check(EngineLanSession.latest.connectCount==0,"Choosing a mode must not connect automatically")
            action(menu,"Remote").tap(from:controller);spin(0.37)
            check(choices==1 && ui.connectionTitle=="Remote","Remote selected exactly once")
            let roles=alert(controller)
            check(roles.actions.map { $0.title! } == ["Join a game","Create lobby","Cancel"],"Remote offers both roles")
            action(roles,"Join a game").tap(from:controller);spin(0.37)
            let form=alert(controller)
            check(form.title=="Multiplayer · Remote" && form.textFields?.count==3,"Remote connection form")
            check(form.message?.contains("Tailscale")==true,"Explain VPN and host requirement")
            if scenario=="remote-invalid" {
                form.textFields![0].text="192.168.1.5"
                action(form,"Connect").tap(from:controller);spin(0.37)
                check(EngineLanSession.latest.connectCount==0,"Remote rejects Wi-Fi endpoint before connection")
                check(alert(controller).message?.contains("Tailscale 100.x")==true,"Actionable remote validation")
                print("REMOTE_MODE_REJECTS_LOCAL_ADDRESS_PASS")
                print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM")
                return
            }
            form.textFields![0].text="100.70.1.9"
        } else {
            ui.present(from:controller,running:false)
        }
        let initial=alert(controller)
        check(initial.textFields?.count==3,"Setup form must retain its three fields")
        check(initial.message?.contains("Room: LOS-SANTOS")==true,"Show the room in the connection summary")
        if scenario == "rename-failure" {
            initial.textFields![2].text="New Name"
            action(initial,"Connect").tap(from:controller);spin(0.37)
            check(EngineLanSession.latest.connectCount==0 && profileDisplayName=="zema","Persistence failure must block admission and retain the old name")
            check(alert(controller).message?.contains("Existing data was preserved")==true,"Failure explains preserved profile")
            print("NATIVE_RENAME_FAILURE_BLOCKS_ADMISSION_PASS");print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM");return
        }
        action(initial,"Connect").tap(from:controller)
        let session=EngineLanSession.latest!
        check(session.connectCount==1,"Initial action must start one transport attempt")
        check(controller.presentedViewController==nil,"Connect action dismisses initial panel")
        switch CommandLine.arguments[1] {
        case "remote-success":
            check(session.connectCount==1,"Remote starts exactly one attempt")
            check(testPreferences.string(forKey:EngineLanPreferences.remoteRelayKey)=="ws://100.70.1.9:47540/engine-lan","Remember remote address")
            check(testPreferences.string(forKey:EngineLanPreferences.relayKey)==nil,"Remote must not overwrite LAN address")
            session.result("Fixture remote admitted.",admitted:true);spin(0.47)
            check(ui.ready && controller.presentedViewController==nil,"Remote success returns home without repeated prompt")
            ui.presentChoices(from:controller) {}
            action(alert(controller),"LAN").tap(from:controller);spin(0.37)
            check(ui.connectionTitle=="Remote" && ui.ready,"Cannot mutate an admitted session by switching modes")
            check(alert(controller).message?.contains("saved character is preserved")==true,"Switch explains restart and save preservation")
            print("REMOTE_SUCCESS_PRESERVES_LAN_AND_ACTIVE_SESSION_PASS")
        case "saved-name-retry":
            check(session.admittedNames==["zema"],"Initial admission uses the saved character name")
            check(profileLoadCount==1 && profileCommitCount==0 && profileConfigureCount==0,"Loading an existing profile preserves its identity and saved bytes")
            session.result("Fixture first admission failed.");spin(0.47)
            let retry=alert(controller)
            check(retry.message?.contains("chosen name updates the saved multiplayer name")==true,"Setup explains rename with preserved progress")
            retry.textFields![2].text="Other name"
            action(retry,"Connect").tap(from:controller)
            check(session.admittedNames==["zema","Other name"],"Explicit Join name reaches relay after profile rename")
            check(profileLoadCount==1 && profileCommitCount==1 && profileConfigureCount==0,"Rename persists existing profile without configuring a new identity")
            session.result("Fixture retry admitted.",admitted:true);spin(0.47)
            check(ui.ready && controller.presentedViewController==nil,"Renamed admission retains the successful home flow")
            ui.present(from:controller,running:false)
            let edit=alert(controller);edit.textFields![2].text="Later edit";action(edit,"Reconnect").tap(from:controller);spin(0.37)
            check(session.connectCount==2 && profileDisplayName=="Other name","Admitted edit cannot mutate profile or connect")
            action(alert(controller),"OK").tap(from:controller)
            session.result("Disconnected");spin(0.03);ui.present(from:controller,running:true)
            action(alert(controller),"Reconnect").tap(from:controller)
            check(session.admittedNames==["zema","Other name","Other name"],"Reconnect ignores rejected later field edit")
            print("NATIVE_SAVED_PROFILE_NAME_RETRY_PASS")
        case "fast-failure":
            // This result arrives well before the production 0.4 s re-presentation.
            DispatchQueue.main.asyncAfter(deadline:.now()+0.02) {
                session.result("Fast fixture join failure: peer rejected admission.")
            }
            spin(0.47)
            let panel=alert(controller)
            check(panel.message?.hasPrefix("Fast fixture join failure: peer rejected admission.")==true,"Fast failure must survive later panel creation")
            check(action(panel,"Connect").isEnabled,"A failed attempt must allow retry")
            check(!ui.ready,"Failure must not claim game readiness")
            print("NATIVE_FAST_CONNECTION_FAILURE_PRESENTATION_PASS")
        case "pending-then-success":
            spin(0.47)
            check(controller.presentedViewController==nil,"Pending setup must not reopen its form")
            ui.present(from:controller,running:false)
            check(controller.presentedViewController==nil,"Play/setup while pending must not stack another form")
            var starts=0
            check(ui.waitForConnection { starts+=100 },"Play may wait for admission")
            check(ui.waitForConnection { starts+=1 },"Repeated Play keeps just one intent")
            session.result("Fixture delayed join failure.");spin(0.47)
            let panel=alert(controller),connect=action(panel,"Connect")
            check(panel.message?.hasPrefix("Fixture delayed join failure.")==true,"Failure must show its actual reason")
            check(starts==0 && connect.isEnabled,"Failure must discard deferred launch and allow retry")
            connect.tap(from:controller)
            check(session.connectCount==2,"Retry should create exactly one new attempt")
            check(ui.waitForConnection { starts+=1 },"Explicit Play during retry may wait")
            session.result("Fixture transport admitted.",admitted:true);spin(0.47)
            check(ui.ready,"Successful admission and prepared profile must enable game startup")
            check(controller.presentedViewController==nil,"Success must stay on home without Reconnect prompt")
            check(starts==1,"Exactly one explicit Play intent must continue")
            session.result("Fixture duplicate admission.",admitted:true);spin(0.47)
            check(starts==1,"Duplicate readiness must not launch twice")
            check(!ui.waitForConnection { starts+=100 },"Ready Play should follow the regular startup path")
            print("NATIVE_PENDING_CONNECTION_ACTION_GUARD_AND_READY_CLOSE_PASS")
        case "fast-success":
            session.result("Fixture fast admission.",admitted:true);spin(0.47)
            check(ui.ready && controller.presentedViewController==nil,"Fast success must not reopen a Reconnect form")
            check(session.connectCount==1,"Success must not reconnect automatically")
            print("NATIVE_FAST_SUCCESS_STAYS_HOME_PASS")
        case "leave-before-retry":
            var starts=0
            check(ui.waitForConnection { starts+=1 },"Play waits while connecting")
            session.result("Fixture failed admission.");spin(0.03)
            ui.leaveBeforeOfflineLaunch();spin(0.47)
            check(controller.presentedViewController==nil && starts==0,"Offline selection cancels pending retry form and Play")
            print("NATIVE_LEAVE_CANCELS_PENDING_PRESENTATION_AND_PLAY_PASS")
        case "running-reconnect", "settings-reconnect-fast", "settings-reconnect-failure", "settings-reconnect-connected":
            session.result("Fixture initial admission.",admitted:true);spin(0.03)
            check(controller.presentedViewController==nil,"Initial admission stays at home")
            if scenario == "settings-reconnect-connected" {
                ui.reconnectSession(from:controller);spin(0.5)
                check(sessionRestartRequests==1 && session.connectCount==1,"Connected Settings action restarts GTA without another transport")
                check(controller.presentedViewController==nil,"Connected Settings action must not open a confirmation")
            } else {
                session.result("Fixture relay disconnected.");spin(0.03)
                if scenario == "running-reconnect" {
                    ui.present(from:controller,running:true)
                    action(alert(controller),"Reconnect").tap(from:controller)
                } else { ui.reconnectSession(from:controller) }
                ui.reconnectSession(from:controller)
                check(session.connectCount==2,"Duplicate reconnect while pending must not open another transport")
                if scenario == "settings-reconnect-failure" {
                    session.result("Fixture actual host admission failed.");spin(0.5)
                    check(sessionRestartRequests==0,"Failed transport must not restart GTA")
                    check(alert(controller).message?.contains("actual host admission failed")==true,"Actual failure retains its reason")
                    check(!alert(controller).actions.contains(where:{$0.title=="Reconnect"}),"Failure is feedback, not a second reconnect confirmation")
                } else {
                    if scenario == "running-reconnect" {
                        spin(0.5)
                        check(controller.presentedViewController==nil,"Delayed reconnect must not open the old connection panel")
                    }
                    session.result("Fixture resumed transport.",admitted:true);spin(0.5)
                    check(sessionRestartRequests==1 && controller.presentedViewController==nil,"Success queues one restart without another confirmation")
                    session.result("Fixture duplicate admission.",admitted:true);spin(0.5)
                    check(sessionRestartRequests==1 && controller.presentedViewController==nil,"Duplicate success must not restart or present twice")
                    ui.present(from:controller,running:true)
                    check(action(alert(controller),"Reconnect").isEnabled,"Explicit globe details remain available")
                    action(alert(controller),"Close").tap(from:controller)
                }
            }
            print("NATIVE_RECONNECT_NO_DUPLICATE_PANEL_\(scenario)_PASS")
        default:exit(2)
        }
        print("OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM")
    }
}
'''


class NativeConnectionPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='zema-native-connection-ui-')
        cls.directory=Path(cls.temporary.name).resolve()
        cls.binary=cls.directory/'connection-ui-fixture'
        source=(ROOT/'EngineLanLabUI.swift').read_text()
        # Compile actual production code. No presentation logic is rewritten.
        source=source.replace('import UIKit\n','').replace('import ZemaLanBackend\n','').replace('UserDefaults.standard','testPreferences')
        fixture=cls.directory/'connection-ui.swift'
        preferences=(ROOT/'EngineLanPreferences.swift').read_text().replace('UserDefaults.standard','testPreferences')
        invitation=(ROOT/'LobbyInvitation.swift').read_text().split('enum LobbyHistory')[0]
        browser='''enum LobbyHistory { static func remember(_ record:LobbyRecord) {} }
enum LobbyBrowserPresenter {
    static var selection: ((LobbyRecord)->Void)?
    static func present(from:UIViewController,selected:@escaping(LobbyRecord)->Void) { selection=selected }
}
'''
        checkpoint=(ROOT/'EngineLanProfileCheckpoint.swift').read_text()
        fixture.write_text(DOUBLES+'\n'+preferences+'\n'+invitation+'\n'+browser+'\n'+checkpoint+'\n'+source+'\n'+HARNESS)
        result=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-parse-as-library',
            '-module-cache-path',str(cls.directory/'cache'),str(fixture),'-o',str(cls.binary)],
            capture_output=True,text=True,timeout=90)
        if result.returncode:raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def execute(self,scenario,marker):
        result=subprocess.run([str(self.binary),scenario],capture_output=True,text=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn(marker,result.stdout)
        self.assertIn('OFFLINE_UI_LOGIC_ONLY_NO_DEVICE_OR_GAMEPLAY_CLAIM',result.stdout)

    def test_merged_host_setup_waits_for_final_green_action(self):
        self.execute("choose-host","FINAL_GREEN_GATE_PASS")

    def test_browsed_lobby_waits_for_final_green_action(self):
        self.execute("browse-final","FINAL_GREEN_GATE_PASS")

    def test_failed_name_persistence_blocks_admission(self):
        self.execute("rename-failure","NATIVE_RENAME_FAILURE_BLOCKS_ADMISSION_PASS")

    def test_play_reuses_saved_lobby_without_setup_and_launches_once(self):
        self.execute("saved-ready","SAVED_PLAY_PASS")

    def test_first_play_stays_home_without_duplicate_chooser(self):
        self.execute("saved-empty","SAVED_PLAY_PASS")

    def test_join_setup_waits_for_final_green_action(self):
        self.execute('quick-join','QUICK_JOIN_PASS')

    def test_pasted_invite_selects_remote_and_decodes_room(self):
        self.execute('quick-invite','QUICK_JOIN_PASS')

    def test_cancel_does_not_leak_quick_launch(self):
        self.execute('quick-cancel','QUICK_CANCEL_PASS')

    def test_remote_can_host_on_phone_without_mac_join_preferences(self):
        self.execute('host-remote','PHONE_HOST_UI_host-remote_PASS')

    def test_remote_hosts_on_cellular_with_vpn_listener_and_no_wifi(self):
        self.execute('host-remote-cellular','PHONE_HOST_UI_host-remote-cellular_PASS')

    def test_remote_listener_error_retains_os_reason_without_wifi_advice(self):
        self.execute('host-remote-failure','PHONE_HOST_UI_host-remote-failure_PASS')

    def test_host_success_shares_address_preserves_join_settings_and_stops(self):
        self.execute('host-success','PHONE_HOST_UI_host-success_PASS')

    def test_background_stops_host_and_restores_idle_timer(self):
        self.execute('host-background','PHONE_HOST_UI_host-background_PASS')

    def test_failed_host_does_not_launch_or_hold_idle_timer(self):
        self.execute('host-failure','PHONE_HOST_UI_host-failure_PASS')

    def test_remote_success_preserves_lan_settings_and_active_session(self):
        self.execute('remote-success','REMOTE_SUCCESS_PRESERVES_LAN_AND_ACTIVE_SESSION_PASS')

    def test_remote_rejects_wifi_address_before_attempting_connection(self):
        self.execute('remote-invalid','REMOTE_MODE_REJECTS_LOCAL_ADDRESS_PASS')

    def test_fast_failure_before_panel_creation_stays_visible(self):
        self.execute('fast-failure','NATIVE_FAST_CONNECTION_FAILURE_PRESENTATION_PASS')

    def test_pending_action_guard_delayed_failure_retry_and_ready_close(self):
        self.execute('pending-then-success','NATIVE_PENDING_CONNECTION_ACTION_GUARD_AND_READY_CLOSE_PASS')

    def test_fast_success_does_not_reopen_connection_form(self):
        self.execute('fast-success','NATIVE_FAST_SUCCESS_STAYS_HOME_PASS')

    def test_leaving_for_offline_cancels_queued_retry_and_play(self):
        self.execute('leave-before-retry','NATIVE_LEAVE_CANCELS_PENDING_PRESENTATION_AND_PLAY_PASS')

    def test_running_reconnect_disabled_while_pending_and_after_admission(self):
        self.execute('running-reconnect','NATIVE_RECONNECT_NO_DUPLICATE_PANEL_running-reconnect_PASS')

    def test_settings_reconnect_fast_success_has_no_second_confirmation(self):
        self.execute('settings-reconnect-fast','NATIVE_RECONNECT_NO_DUPLICATE_PANEL_settings-reconnect-fast_PASS')

    def test_settings_reconnect_connected_has_no_second_confirmation(self):
        self.execute('settings-reconnect-connected','NATIVE_RECONNECT_NO_DUPLICATE_PANEL_settings-reconnect-connected_PASS')

    def test_settings_reconnect_failure_reports_reason_without_reconfirming(self):
        self.execute('settings-reconnect-failure','NATIVE_RECONNECT_NO_DUPLICATE_PANEL_settings-reconnect-failure_PASS')

    def test_retry_uses_saved_profile_name_without_mutating_identity(self):
        self.execute('saved-name-retry','NATIVE_SAVED_PROFILE_NAME_RETRY_PASS')


if __name__=='__main__':unittest.main()
