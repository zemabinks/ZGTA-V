import Foundation
import CoreFoundation

struct LobbyHealth {
    struct Room {let name:String;let players:Int;let slots:Int;let capacity:Int}
    let online:Bool
    let incompatible:Bool
    let players:Int
    let rooms:[Room]
    let catalog:Bool
    let restricted:Bool
    let latency:Int
    static func decode(_ data:Data,latency:Int)->LobbyHealth? {
        guard data.count<=16384,let object=try? JSONSerialization.jsonObject(with:data) as? [String:Any],object["service"] as? String=="zgta-engine-lan" else{return nil}
        guard object["protocol"] as? String=="zema-engine-lan/1",object["build"] as? String=="8b0b5899ed" else{return LobbyHealth(online:false,incompatible:true,players:0,rooms:[],catalog:false,restricted:false,latency:latency)}
        func integer(_ value:Any?,maximum:Int)->Int?{guard let number=value as? NSNumber,CFGetTypeID(number) != CFBooleanGetTypeID(),number.doubleValue.rounded()==number.doubleValue,number.doubleValue>=0,number.doubleValue<=Double(maximum) else{return nil};return number.intValue}
        guard let players=integer(object["peers"],maximum:1024),integer(object["rooms"],maximum:32) != nil,let instance=object["instance"] as? String,instance.range(of:"^[a-f0-9]{32}$",options:.regularExpression) != nil else{return nil}
        var rooms:[Room]=[];var seen=Set<String>();let catalog=integer(object["catalog_version"],maximum:1)==1
        if catalog {
            guard let rows=object["lobbies"] as? [[String:Any]],rows.count<=32 else{return nil}
            for row in rows {
                guard let room=row["room"] as? String,EngineLanPreferences.validRoom(room),seen.insert(room).inserted,let active=integer(row["players"],maximum:32),let slots=integer(row["slots"],maximum:32),let capacity=integer(row["capacity"],maximum:32),capacity>0,active<=slots,slots<=capacity else{return nil}
                rooms.append(Room(name:room,players:active,slots:slots,capacity:capacity))
            }
        }
        return LobbyHealth(online:true,incompatible:false,players:players,rooms:rooms,catalog:catalog,restricted:object["room_policy"] as? String=="hosted",latency:latency)
    }
}

/// Bounded read-only request. No redirects, cookies, credentials or game admission.
final class LobbyHealthProbe:NSObject,URLSessionDataDelegate,URLSessionTaskDelegate,@unchecked Sendable {
    private var session:URLSession?
    private var body=Data()
    private var completion:((LobbyHealth?)->Void)?
    private let started=ProcessInfo.processInfo.systemUptime
    init(record:LobbyRecord,completion:@escaping(LobbyHealth?)->Void){
        super.init();self.completion=completion
        guard let source=EngineLanSession.validEndpoint(record.relay),var url=URLComponents(url:source,resolvingAgainstBaseURL:false) else{finish(nil);return}
        url.scheme="http";url.path="/health"
        guard let endpoint=url.url else{finish(nil);return}
        let configuration=URLSessionConfiguration.ephemeral;configuration.timeoutIntervalForRequest=2.5;configuration.timeoutIntervalForResource=2.5;configuration.httpCookieStorage=nil;configuration.urlCredentialStorage=nil;configuration.httpShouldSetCookies=false;configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        let queue=OperationQueue();queue.maxConcurrentOperationCount=1
        let session=URLSession(configuration:configuration,delegate:self,delegateQueue:queue);self.session=session
        session.dataTask(with:endpoint).resume()
    }
    func cancel(){session?.invalidateAndCancel()}
    private func finish(_ health:LobbyHealth?){
        guard let callback=completion else{return};completion=nil;let current=session;session=nil;current?.invalidateAndCancel()
        DispatchQueue.main.async{callback(health)}
    }
    func urlSession(_ session:URLSession,task:URLSessionTask,willPerformHTTPRedirection response:HTTPURLResponse,newRequest request:URLRequest,completionHandler:@escaping(URLRequest?)->Void){completionHandler(nil)}
    func urlSession(_ session:URLSession,dataTask:URLSessionDataTask,didReceive response:URLResponse,completionHandler:@escaping(URLSession.ResponseDisposition)->Void){
        guard let response=response as? HTTPURLResponse,response.statusCode==200,response.mimeType=="application/json",response.expectedContentLength<=16384 else{completionHandler(.cancel);return}
        completionHandler(.allow)
    }
    func urlSession(_ session:URLSession,dataTask:URLSessionDataTask,didReceive data:Data){
        guard body.count+data.count<=16384 else{finish(nil);return};body.append(data)
    }
    func urlSession(_ session:URLSession,task:URLSessionTask,didCompleteWithError error:Error?){
        let latency=Int(max(0,(ProcessInfo.processInfo.systemUptime-started)*1000));finish(error==nil ? LobbyHealth.decode(body,latency:latency):nil)
    }
}
