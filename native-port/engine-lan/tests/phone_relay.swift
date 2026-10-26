import Foundation
import Darwin

func packet(_ source: UInt32, _ destination: UInt32) -> Data {
    func bytes(_ x: UInt32) -> [UInt8] { [UInt8(x >> 24),UInt8((x >> 16)&255),UInt8((x >> 8)&255),UInt8(x&255)] }
    return Data([71,53,1,3] + bytes(source) + [1,2] + bytes(destination) + [1,2,99,100])
}
func join(_ room: String = "PHONE-TEST", _ name: String = "Fixture", resume: String? = nil) -> Data {
    var value: [String:Any] = ["type":"join","protocol":PhoneRelayWire.version,"build":PhoneRelayWire.build,"room":room,"name":name]
    if let resume { value["resume"] = resume }; return try! PhoneRelayWire.json(value)
}
func decoded(_ data: Data) -> [String:Any] { try! JSONSerialization.jsonObject(with:data) as! [String:Any] }
func refuses(_ body: () throws -> Void) { do { try body();fatalError("Unexpected acceptance") } catch {} }
func coreChecks() {
    for address in ["127.0.0.1","10.1.2.3","172.16.0.1","172.31.255.254","192.168.1.2","169.254.3.4","100.64.0.1","100.127.255.254"] { precondition(PhoneRelayWire.privateIPv4(address)) }
    for address in ["0.0.0.0","8.8.8.8","172.15.1.1","172.32.1.1","100.63.1.1","100.128.1.1","100.064.0.1","localhost","::1","192.168.1.2\n"] { precondition(!PhoneRelayWire.privateIPv4(address)) }
    let header=Data("GET /engine-lan HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n".utf8)
    precondition(String(data:try! PhoneRelayWire.header(header).response,encoding:.utf8)!.contains("s3pPLMBiTxaQ9kYGzzhZRbK+xOo="))
    refuses { _ = try PhoneRelayWire.header(Data("GET /bad HTTP/1.1\r\n\r\n".utf8)) }
    refuses { _ = try PhoneRelayWire.header(Data("GET /health HTTP/1.1\r\nOrigin: https://hostile.example\r\n\r\n".utf8)) }
    refuses { _ = try PhoneRelayWire.header(Data("GET /health HTTP/1.1\r\nHost: a\r\nhost: b\r\n\r\n".utf8)) }
    for bytes: [UInt8] in [[0x01,0x80],[0xc1,0x80],[0x81,0x00],[0x81,0xff],[0x81,0xfe,0,1],[0x81,0xfe,8,1],[0x88,0x81,0,0,0,0,0]] {
        var buffer=Data(bytes);refuses { _ = try PhoneRelayWire.nextFrame(&buffer) }
    }
    let body=Array("hello".utf8), mask: [UInt8]=[1,2,3,4]
    let framed: [UInt8]=[0x81,0x85]+mask+body.enumerated().map { $0.element ^ mask[$0.offset%4] }
    var buffer=Data()
    for byte in framed.dropLast() { buffer.append(byte);precondition(try! PhoneRelayWire.nextFrame(&buffer)==nil) }
    buffer.append(framed.last!);let frame=try! PhoneRelayWire.nextFrame(&buffer);precondition(frame?.payload==Data(body) && buffer.isEmpty)
    var now:TimeInterval=10
    let core=PhoneRelayCore(room:"PHONE-TEST",now:{now}),a=UUID(),b=UUID()
    let first=decoded(try! core.admit(join(),connection:a).joined),second=decoded(try! core.admit(join("PHONE-TEST","Other"),connection:b).joined)
    let avip=(first["vip"] as! NSNumber).uint32Value,bvip=(second["vip"] as! NSNumber).uint32Value
    precondition(core.online==2 && first["epoch"] as! String==second["epoch"] as! String && avip != bvip)
    precondition(try! core.destinations(packet(avip,bvip),from:a)==[b])
    precondition(try! core.destinations(packet(avip,UInt32.max),from:a)==[b])
    refuses { _ = try core.destinations(packet(bvip,avip),from:a) }
    refuses { _ = try core.admit(join("DIFFERENT-ROOM"),connection:UUID()) }
    refuses { _ = try core.admit(join("PHONE-TEST","bad\nname"),connection:UUID()) }
    core.depart(a);now+=19
    let replacement=UUID(),resumed=try! core.admit(join(resume:first["resume"] as? String),connection:replacement)
    precondition(decoded(resumed.joined)["vip"] as! NSNumber==first["vip"] as! NSNumber)
    core.depart(a);precondition(core.online==2,"Old departure cannot evict a resumed peer")
    let newer=UUID(),takeover=try! core.admit(join(resume:first["resume"] as? String),connection:newer)
    precondition(takeover.replaced==replacement)
    refuses { _ = try core.destinations(packet(avip,bvip),from:replacement) }
    core.depart(newer);now+=21;core.expire()
    refuses { _ = try core.admit(join(resume:first["resume"] as? String),connection:UUID()) }
    let fresh=PhoneRelayCore(room:"PHONE-TEST")
    var recovery=decoded(join());recovery["rejoin"]=["vip":avip,"epoch":fresh.epoch]
    let recovered=decoded(try! fresh.admit(try! PhoneRelayWire.json(recovery),connection:UUID()).joined)
    precondition(recovered["vip"] as! NSNumber == first["vip"] as! NSNumber)
    refuses { _ = try fresh.admit(try PhoneRelayWire.json(recovery),connection:UUID()) }
    recovery["rejoin"]=["vip":bvip,"epoch":String(repeating:"0",count:16)]
    refuses { _ = try fresh.admit(try PhoneRelayWire.json(recovery),connection:UUID()) }
    precondition(fresh.online==1)
    for _ in 0..<7 { _ = try! core.admit(join(),connection:UUID()) }
    precondition(core.online==8)
    refuses { _ = try core.admit(join(),connection:UUID()) }
    now+=2
    for _ in 0..<4096 { _ = try! core.destinations(packet(bvip,UInt32.max),from:b) }
    refuses { _ = try core.destinations(packet(bvip,UInt32.max),from:b) }
    now+=1;_ = try! core.destinations(packet(bvip,UInt32.max),from:b)
    print("PHONE_RELAY_CORE_BOUNDS_RESUME_EXPIRY_SPOOFING_RATE_WIRE_PASS")
}
final class PairedState: @unchecked Sendable {
    let lock=NSLock();var vips:[Int:UInt32]=[:];var epochs:[Int:UInt64]=[:];var sent=false
    func configure(_ index:Int,_ vip:UInt32,_ epoch:UInt64) -> Bool {
        lock.lock();defer{lock.unlock()};vips[index]=vip;epochs[index]=epoch;return true
    }
    func outgoing(_ index:Int) -> Data? {
        lock.lock();defer{lock.unlock()}
        guard index==0,!sent,let a=vips[0],let b=vips[1] else{return nil};sent=true;return packet(a,b)
    }
    func deliver(_ index:Int,_ data:Data) {
        lock.lock();defer{lock.unlock()}
        precondition(index==1 && epochs[0]==epochs[1] && data==packet(vips[0]!,vips[1]!))
        print("NATIVE_URLSESSION_TWO_CLIENTS_PHONE_HOST_PROTOCOL_PASS");fflush(stdout);exit(0)
    }
}
@main struct PhoneRelayFixture {
    static var server:PhoneRelayServer?
    static var clients:[EngineLanSession]=[]
    static func main() {
        if CommandLine.arguments[1]=="core" { coreChecks();return }
        let port=UInt16(CommandLine.arguments[2])!,relay=PhoneRelayServer();server=relay
        var addresses = ["127.0.0.1"]
        if CommandLine.arguments[1] == "dual-serve" {
            let detected = PhoneRelayAddresses.current()
            guard let extra = detected.lan ?? detected.vpn else { print("SKIP_NO_PRIVATE_INTERFACE");return }
            addresses.append(extra)
        }
        relay.start(addresses:addresses,room:"PHONE-TEST",port:port) { result in
            if CommandLine.arguments[1] == "failure" {
                guard case .failure(let error) = result else { fputs("EXPECTED_BIND_FAILURE\n",stderr);exit(4) }
                print("ACTUAL_LISTENER_FAILURE: " + error.localizedDescription);fflush(stdout);exit(0)
            }
            guard case .success=result else{fputs("LISTENER_FAILED\n",stderr);exit(2)}
            if CommandLine.arguments[1]=="sessions" {
                let state=PairedState()
                for index in 0..<2 {
                    let client=EngineLanSession(backend:.init(configure:{state.configure(index,$0,$1)},connected:{_ in},deliver:{state.deliver(index,$0)},outgoing:{state.outgoing(index)}))
                    clients.append(client);client.connect(endpoint:"ws://127.0.0.1:\(port)/engine-lan",room:"PHONE-TEST",name:"Native\(index)")
                }
                DispatchQueue.main.asyncAfter(deadline:.now()+10){fputs("PAIRED_NATIVE_TIMEOUT\n",stderr);exit(3)}
            } else { print("PHONE_RELAY_READY");fflush(stdout) }
        }
        dispatchMain()
    }
}
