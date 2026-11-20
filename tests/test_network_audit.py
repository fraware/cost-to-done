"""Adversarial static topology checks; Docker integration is a separate test."""
from __future__ import annotations

import copy
import unittest

from cost_to_done.core import ReceiptError
from cost_to_done.network_audit import audit_live_compose


class NetworkAuditTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "services": {
                "main": {"image": "python:3.12", "networks": {"ctd_agent_net": None},
                         "cap_drop": ["ALL"], "cap_add": ["FOWNER", "DAC_OVERRIDE"],
                         "security_opt": ["no-new-privileges:true"]},
                "ctd_gateway": {"image": "python:3.12", "networks": {"ctd_agent_net": None, "ctd_provider_net": None},
                                 "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
                                 "read_only": True, "environment": {"CTD_GATEWAY_TOKEN": "secret", "CTD_BUDGET_USD": "0.25"},
                                 "secrets": [{"source": "ctd_provider_key", "target": "/run/secrets/ctd_provider_key"}]},
            },
            "secrets": {"ctd_provider_key": {"file": "/tmp/operator-key"}},
            "networks": {"ctd_agent_net": {"internal": True}, "ctd_provider_net": {}},
        }

    def test_valid_topology(self):
        result = audit_live_compose(self.config)
        self.assertTrue(result["agent_network_internal"])
        self.assertIn("static", result["status"])
        self.assertNotIn("/tmp/operator-key", str(result))

    def test_provider_network_on_agent_rejected(self):
        self.config["services"]["main"]["networks"]["ctd_provider_net"] = None
        with self.assertRaisesRegex(ReceiptError, "outside"):
            audit_live_compose(self.config)

    def test_public_agent_network_rejected(self):
        self.config["networks"]["ctd_agent_net"]["internal"] = False
        with self.assertRaisesRegex(ReceiptError, "internal"):
            audit_live_compose(self.config)

    def test_main_provider_secret_mount_rejected(self):
        self.config["services"]["main"]["secrets"] = ["ctd_provider_key"]
        with self.assertRaisesRegex(ReceiptError, "secrets"):
            audit_live_compose(self.config)

    def test_host_mount_rejected(self):
        self.config["services"]["main"]["volumes"] = ["/var/run/docker.sock:/var/run/docker.sock"]
        with self.assertRaisesRegex(ReceiptError, "mount"):
            audit_live_compose(self.config)

    def test_published_gateway_port_rejected(self):
        self.config["services"]["ctd_gateway"]["ports"] = [{"published": 8866, "target": 8866}]
        with self.assertRaisesRegex(ReceiptError, "ports"):
            audit_live_compose(self.config)

    def test_privileged_execution_rejected(self):
        self.config["services"]["main"]["privileged"] = True
        with self.assertRaisesRegex(ReceiptError, "privilege"):
            audit_live_compose(self.config)

    def test_docker_socket_and_host_pid_rejected(self):
        self.config["services"]["ctd_gateway"]["pid"] = "host"
        with self.assertRaisesRegex(ReceiptError, "host-namespace"):
            audit_live_compose(self.config)

    def test_net_admin_rejected(self):
        self.config["services"]["main"]["cap_add"].append("NET_ADMIN")
        with self.assertRaisesRegex(ReceiptError, "capability"):
            audit_live_compose(self.config)

    def test_gateway_without_secret_rejected(self):
        self.config["services"]["ctd_gateway"]["secrets"] = []
        with self.assertRaisesRegex(ReceiptError, "secret"):
            audit_live_compose(self.config)

    def test_extra_service_rejected(self):
        self.config["services"]["untrusted"] = {"image": "busybox"}
        with self.assertRaisesRegex(ReceiptError, "unexpected"):
            audit_live_compose(self.config)

    def test_environment_provider_key_rejected(self):
        self.config["services"]["main"]["environment"] = {"OPENAI_API_KEY": "bad"}
        with self.assertRaisesRegex(ReceiptError, "credential"):
            audit_live_compose(self.config)

    def test_provider_egress_network_removed_rejected(self):
        del self.config["services"]["ctd_gateway"]["networks"]["ctd_provider_net"]
        with self.assertRaisesRegex(ReceiptError, "bridge"):
            audit_live_compose(self.config)


if __name__ == "__main__":
    unittest.main()
