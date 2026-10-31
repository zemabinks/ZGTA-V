"""Managed empty-room presence and owned LAN announcement lifecycle."""
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'relay-service'))
import relay
import lobby_directory
import service_runner as runner


class EmptyHostedRoom(unittest.TestCase):
    def test_default_room_stays_after_last_reservation_expires_and_other_rooms_remain_open(self):
        clock = [0]
        engine = relay.Relay(clock=lambda: clock[0], advertised_room='LOS-SANTOS')
        empty = engine.health()
        self.assertEqual((empty['peers'], empty['rooms'], empty['room_policy']), (0,1,'open'))
        self.assertEqual(empty['lobbies'], [dict(room='LOS-SANTOS',players=0,slots=0,capacity=32,player_names=[])])
        self.assertEqual(lobby_directory.checked_health(empty)['lobbies'][0]['room'], 'LOS-SANTOS')
        for room in ['LOS-SANTOS', 'ANOTHER-ROOM']:
            peer, generation = engine.admit(dict(type='join',protocol=relay.PROTOCOL,build=relay.BUILD,room=room,name='Test'),object())
            self.assertIn(room, [x['room'] for x in engine.health()['lobbies']])
            engine.depart(peer, generation)
        clock[0] = relay.TTL + 1
        self.assertEqual(engine.health()['lobbies'], empty['lobbies'])
        self.assertEqual(engine.rooms, {})

    def test_full_catalog_is_still_bounded_and_no_duplicate_default(self):
        engine = relay.Relay(advertised_room='LOS-SANTOS')
        for i in range(32):
            engine.admit(dict(type='join',protocol=relay.PROTOCOL,build=relay.BUILD,room=str(i),name='Test'),object())
        health = engine.health()
        self.assertEqual((len(health['lobbies']), health['rooms']), (32,32))
        lobby_directory.checked_health(health)
        self.assertLess(len(json.dumps(health).encode()), 16384)
        default = relay.Relay(advertised_room='LOS-SANTOS')
        default.admit(dict(type='join',protocol=relay.PROTOCOL,build=relay.BUILD,room='LOS-SANTOS',name='Test'),object())
        self.assertEqual(len(default.catalog()),1)

    def test_unconfigured_relays_do_not_invent_rooms_and_invalid_names_fail(self):
        self.assertEqual(relay.Relay().health()['rooms'],0)
        for name in ['', ' ', 'bad\nroom', 'x'*65, True]:
            with self.assertRaises(ValueError): relay.Relay(advertised_room=name)


class ManagedAnnouncement(unittest.TestCase):
    def test_actual_nondefault_port_interface_scoping_and_owned_cleanup(self):
        child = Mock(); child.poll.return_value = None
        spawn = Mock(return_value=child)
        announcement = runner.LANAnnouncement(Mock(),spawn=spawn,interface=lambda address:'en0')
        announcement.ensure('192.168.1.2', 52173)
        args = spawn.call_args.args[0]
        self.assertEqual(args[:5], ['/usr/bin/dns-sd','-i','en0','-P','ZGTA V · LOS-SANTOS'])
        self.assertEqual(args[5:8], ['_zgtav._tcp.','local.','52173'])
        self.assertEqual(args[9], '192.168.1.2')
        self.assertNotIn('0.0.0.0', args)
        announcement.ensure('192.168.1.2',52173)
        spawn.assert_called_once()
        announcement.close()
        child.terminate.assert_called_once(); child.wait.assert_called_once_with(timeout=4)

    def test_announcement_failure_does_not_stop_relay_and_recovers(self):
        child = Mock(); child.poll.return_value = None
        spawn = Mock(side_effect=[OSError('fixture'),child])
        announcement = runner.LANAnnouncement(Mock(),spawn=spawn,interface=lambda address:'en0')
        announcement.ensure('192.168.1.2',47540)
        self.assertIsNone(announcement.child)
        announcement.ensure('192.168.1.2',47540)
        self.assertIs(announcement.child,child)
        announcement.close()

    def test_interface_must_match_actual_private_lan_and_no_vpn_or_public_probe(self):
        run = Mock(return_value=SimpleNamespace(returncode=0,stdout='192.168.1.2\n'))
        with patch.object(runner.socket,'if_nameindex',return_value=[(1,'lo0'),(2,'en0'),(3,'utun1')]):
            self.assertEqual(runner.lan_interface('192.168.1.2',run=run),'en0')
            for address in ['127.0.0.1','100.75.1.2','8.8.8.8','0.0.0.0','hostname']:
                run.reset_mock(); self.assertIsNone(runner.lan_interface(address,run=run)); run.assert_not_called()
        run.assert_not_called()

    def test_supervisor_announces_only_after_owned_child_readiness(self):
        child = SimpleNamespace(poll=Mock(return_value=None),relay_ready=threading.Event())
        announcement = Mock()
        supervisor = runner.RelaySupervisor(Path('/unused'),Mock(),spawn=lambda address:child,stop=Mock(),announcement=announcement)
        supervisor.update('192.168.1.2'); supervisor.update_announcement()
        announcement.ensure.assert_not_called()
        child.relay_ready.set(); supervisor.update_announcement()
        announcement.ensure.assert_called_once_with('192.168.1.2',47540)
        supervisor.update(None); self.assertIs(supervisor.child,child)
        child.poll.return_value=1; supervisor.update(None); supervisor.update_announcement()
        self.assertIsNone(supervisor.child); self.assertGreater(announcement.close.call_count,0)


if __name__ == '__main__': unittest.main()
