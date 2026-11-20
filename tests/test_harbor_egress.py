"""Boundary checks for the Harbor network probe without Docker or credentials."""
from __future__ import annotations

import importlib.util
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_PROBE = Path(__file__).parents[1] / 'tests' / 'harbor' / 'probe_egress.py'
_spec = importlib.util.spec_from_file_location('harbor_probe_egress', _PROBE)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)


class ProbeTests(unittest.TestCase):
    def test_raw_private_address_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'provider-ip.txt'
            path.write_text('172.25.100.19\n')
            self.assertEqual(_probe.provider_ip(path, timeout=.01), '172.25.100.19')

    def test_no_proof_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(_probe.IsolationError):
                _probe.provider_ip(Path(temp)/'missing', timeout=.01)

    def test_public_provider_ip_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'ip'
            path.write_text('1.1.1.1')
            with self.assertRaises(_probe.IsolationError):
                _probe.provider_ip(path, timeout=.01)

    def test_successful_direct_connection_fails_test(self):
        connection = unittest.mock.Mock()
        with patch.object(_probe.socket, 'create_connection', return_value=connection):
            with self.assertRaises(_probe.IsolationError):
                _probe.assert_blocked('127.0.0.1', 8770, label='probe')
        connection.close.assert_called_once()

    def test_connection_error_is_blocked(self):
        with patch.object(_probe.socket, 'create_connection', side_effect=OSError('blocked')):
            _probe.assert_blocked('198.51.100.1', 8770, label='probe')


if __name__ == '__main__':
    unittest.main()
