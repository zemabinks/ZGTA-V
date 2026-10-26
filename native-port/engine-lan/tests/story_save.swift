import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

@main enum StorySaveChecks {
    static func main() throws {
        let folder = URL(fileURLWithPath: CommandLine.arguments[1])
        let cases = try JSONSerialization.jsonObject(with: Data(contentsOf: folder.appendingPathComponent("cases.json"))) as! [[String: Any]]
        var rows: [[String: Any]] = []
        for item in cases {
            let data = Data(base64Encoded: item["data"] as! String)!
            let result = try? StorySave.title(data)
            rows.append(["name":item["name"]!, "title":result as Any? ?? NSNull()])
        }
        let valid = Data(base64Encoded: cases[0]["data"] as! String)!
        func check(_ condition: Bool) { precondition(condition) }
        let fm = FileManager.default
        func root(_ name: String) throws -> URL {
            let url = folder.appendingPathComponent(name)
            try fm.createDirectory(at: url, withIntermediateDirectories: true)
            return url
        }
        func saveFolder(_ root: URL) -> URL { root.appendingPathComponent(StorySave.components.joined(separator: "/")) }
        func mustFail(_ action: () throws -> Void) {
            do { try action(); fatalError("Expected rejection") } catch { }
        }
        let r = try root("slots"), original = Data("keep".utf8)
        let first = try StorySave.install(valid, filename: "SGTA50007", root:r)
        check(first.slot == 8)
        let save = saveFolder(r)
        try original.write(to: save.appendingPathComponent("SGTA50000.BAK"))
        try original.write(to: save.appendingPathComponent("SGTA50015"))
        try original.write(to: save.appendingPathComponent("SGTA50015.bak"))
        let second = try StorySave.install(valid, filename: "SGTA50007", root:r)
        check(second.slot == 2)
        check(try Data(contentsOf: save.appendingPathComponent("SGTA50015")) == original)
        check(try Data(contentsOf: save.appendingPathComponent("SGTA50000.BAK")) == original)
        check(try StorySave.read(save.appendingPathComponent("SGTA50001")) == valid)
        check(StorySave.candidates(filename:"../../SGTA50009",occupied:[]) == Array(0..<15))
        check(StorySave.candidates(filename:"sgta50004.bak",occupied:["sgta50004.BAK","SGTA50000"]).first == 1)
        for n in 0..<15 where ![1,7].contains(n) {
            try original.write(to: save.appendingPathComponent(String(format:"SGTA500%02d",n)))
        }
        mustFail { _ = try StorySave.install(valid, filename:"SGTA50015", root:r) }
        let invalid = try root("invalid")
        mustFail { _ = try StorySave.install(Data([0,1]), filename:"SGTA50000", root:invalid) }
        check(!fm.fileExists(atPath: invalid.appendingPathComponent("userdata").path))
        let linked = try root("linked"), outside = try root("outside")
        try fm.createSymbolicLink(at: linked.appendingPathComponent("userdata"), withDestinationURL:outside)
        mustFail { _ = try StorySave.install(valid, filename:"SGTA50000", root:linked) }
        check(try fm.contentsOfDirectory(atPath:outside.path).isEmpty)
        let partial = try root("partial")
        var calls = 0
        let p = try StorySave.install(valid, filename:"SGTA50003", root:partial,writer:{fd,p,n in
            calls += 1
            if calls == 1 { errno = EINTR; return -1 }
            return StorySave.systemWrite(fd,p,min(128,n))
        })
        check(calls > 2 && p.slot == 4)
        check(try Data(contentsOf:saveFolder(partial).appendingPathComponent("SGTA50003")) == valid)
        let failed = try root("failed")
        calls = 0
        mustFail { _ = try StorySave.install(valid, filename:"SGTA50000", root:failed,writer:{fd,p,n in
            calls += 1
            if calls > 1 { errno = EIO; return -1 }
            return StorySave.systemWrite(fd,p,8)
        }) }
        check(try fm.contentsOfDirectory(atPath:saveFolder(failed).path).isEmpty)
        let syncFailed = try root("sync-failed")
        calls = 0
        mustFail { _ = try StorySave.install(valid, filename:"SGTA50000", root:syncFailed,sync:{fd in
            calls += 1
            if calls == 2 { errno = EIO; return -1 }
            return StorySave.systemSync(fd)
        }) }
        check(try fm.contentsOfDirectory(atPath:saveFolder(syncFailed).path).isEmpty)
        let parallel = try root("parallel"), group = DispatchGroup(), lock = NSLock()
        var slots: [Int] = [], failures = 0
        for _ in 0..<15 {
            group.enter(); DispatchQueue.global().async {
                defer { group.leave() }
                let result = Result { try StorySave.install(valid, filename:"SGTA50000",root:parallel) }
                lock.lock(); defer { lock.unlock() }
                switch result { case .success(let item): slots.append(item.slot); case .failure: failures += 1 }
            }
        }
        check(group.wait(timeout:.now()+10) == .success)
        check(failures == 0 && Set(slots) == Set(1...15))
        let output = try JSONSerialization.data(withJSONObject:rows,options:[.sortedKeys])
        print(String(data:output,encoding:.utf8)!)
    }
}
