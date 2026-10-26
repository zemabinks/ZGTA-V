#[path = "../../../src/proto.rs"] mod proto;
#[path = "../../../src/server.rs"] mod server;
fn main() -> std::io::Result<()> {
    let args: Vec<_> = std::env::args().collect();
    server::run(args.get(1).and_then(|s| s.parse().ok()).unwrap_or(proto::DEFAULT_PORT), args.get(2).and_then(|s| s.parse().ok()).unwrap_or(proto::MAX_ROOM_PLAYERS))
}
