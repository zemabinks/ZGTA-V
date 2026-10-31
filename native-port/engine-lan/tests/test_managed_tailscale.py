"""Bounded managed VPN discovery and same-instance listener checks."""
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'relay-service')]
import relay
import service_runner as runner
import relay_control as control

class ManagedVPN(unittest.TestCase):
    def test_existing_client_discovery_is_read_only_and_requires_online_private_ip(self):
        with tempfile.TemporaryDirectory() as d:
            client=Path(d)/'client';client.write_text('fixture');client.chmod(0o700)
            def result(state='Running',online=True,ips=None):
                return SimpleNamespace(returncode=0,stdout=json.dumps({'BackendState':state,'Self':{'Online':online,'TailscaleIPs':ips or ['100.70.1.9']}}))
            run=Mock(return_value=result())
            self.assertEqual(runner.tailscale_ip(run,client),'100.70.1.9')
            self.assertEqual(run.call_args.args[0],[str(client),'status','--json','--peers=false'])
            self.assertEqual(run.call_args.kwargs['env']['TERM'],'dumb')
            for value in [result('Stopped'),result(online=False),result(ips=['8.8.8.8','::1']),SimpleNamespace(returncode=1,stdout=''),SimpleNamespace(returncode=0,stdout='[]')]:
                self.assertIsNone(runner.tailscale_ip(Mock(return_value=value),client))
            client.chmod(0o722);run.reset_mock();self.assertIsNone(runner.tailscale_ip(run,client));run.assert_not_called()
            client.chmod(0o700);link=Path(d)/'link';link.symlink_to(client)
            self.assertIsNone(runner.tailscale_ip(run,link));run.assert_not_called()

    def test_cli_optional_listener_requires_exact_vpn_range(self):
        serve=AsyncMock()
        with patch.object(relay,'serve',serve):relay.main(['--bind','192.168.1.2','--vpn-bind','100.70.1.9','--service'])
        serve.assert_awaited_once_with('192.168.1.2',47540,None,'100.70.1.9')
        for args in [['--vpn-bind','8.8.8.8'],['--vpn-bind','192.168.1.2'],['--tailscale','--bind','100.70.1.9','--vpn-bind','100.70.1.10']]:
            with patch.object(relay,'serve',AsyncMock()) as serve,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):relay.main(args)
            serve.assert_not_called()

    def test_status_requires_live_matching_instance_on_both_addresses(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'runtime';root.mkdir(mode=0o700)
            runner.publish_address(root,'192.168.1.2');runner.publish_address(root,'100.70.1.9','relay-vpn-bind.json')
            health={'instance':'a'*32,'peers':2,'rooms':1}
            with patch.object(control,'ROOT',root),patch.object(control,'verify_agent'),patch.object(control,'loaded',return_value=True),patch.object(control,'health_at',return_value=health),patch.object(control,'browser_host_status',return_value=None):
                state=control.status();self.assertTrue(state['running'] and state['vpn_running']);self.assertEqual(state['peers'],2)
                with patch.object(control,'health_at',side_effect=[health,dict(health,instance='b'*32)]):self.assertFalse(control.status()['vpn_running'])
                with patch.object(control,'health_at',side_effect=[health,{}]):
                    state=control.status();self.assertTrue(state['running']);self.assertFalse(state['vpn_running'])
                with patch.object(control,'health_at',return_value={}):self.assertFalse(control.status()['running'])
                self.assertEqual((root/'relay-vpn-bind.json').stat().st_mode&0o777,0o600)
                runner.publish_address(root,None,'relay-vpn-bind.json');self.assertIsNone(control.published_address(True))
                runner.publish_address(root,'8.8.8.8','relay-vpn-bind.json')
                with self.assertRaises(RuntimeError):control.published_address(True)

class DualListeners(unittest.IsolatedAsyncioTestCase):
    async def test_both_listeners_share_one_relay_and_both_close(self):
        actual=asyncio.get_running_loop();listeners=[]
        def fake():
            item=Mock();item.sockets=[SimpleNamespace(getsockname=lambda:('127.0.0.1',12345))];item.wait_closed=AsyncMock();listeners.append(item);return item
        start=AsyncMock(side_effect=[fake(),fake()])
        loop=SimpleNamespace(add_signal_handler=lambda _sig,fn:actual.call_soon(fn))
        with patch.object(relay.asyncio,'start_server',start),patch.object(relay.asyncio,'get_running_loop',return_value=loop):
            await relay.serve('192.168.1.2',12345,None,'100.70.1.9')
        self.assertIs(start.await_args_list[0].args[0].__self__,start.await_args_list[1].args[0].__self__)
        for listener in listeners:listener.close.assert_called_once();listener.wait_closed.assert_awaited_once()

    async def test_vpn_bind_failure_preserves_lan_until_explicit_stop(self):
        actual=asyncio.get_running_loop();listener=Mock();listener.sockets=[SimpleNamespace(getsockname=lambda:('127.0.0.1',12345))];listener.wait_closed=AsyncMock()
        def schedule(_sig,fn):actual.call_later(.02,fn)
        async def start(*args,**kwargs):
            if args[1]=='100.70.1.9':listener.close.assert_not_called();raise OSError(49,'Unavailable VPN')
            return listener
        with patch.object(relay.asyncio,'start_server',side_effect=start),patch.object(relay.asyncio,'get_running_loop',return_value=SimpleNamespace(add_signal_handler=schedule)):
            await relay.serve('192.168.1.2',12345,None,'100.70.1.9')
        listener.close.assert_called_once();listener.wait_closed.assert_awaited_once()

if __name__=='__main__':unittest.main()
