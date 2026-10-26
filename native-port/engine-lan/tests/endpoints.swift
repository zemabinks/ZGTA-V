import Foundation

@main struct EndpointFixture {
    static func main() throws {
        let rows = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [[String: Any]]
        for row in rows {
            let text = row["url"] as! String
            let expected = row["valid"] as! Bool
            guard (EngineLanSession.validEndpoint(text) != nil) == expected else {
                fputs("Endpoint validation mismatch: \(text.debugDescription)\n", stderr)
                exit(1)
            }
        }
        print("NATIVE_LAN_TAILSCALE_ENDPOINT_BOUNDARIES_PASS \(rows.count)")
    }
}
