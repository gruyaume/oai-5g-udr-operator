# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import ops.testing
from ops.model import ActiveStatus
from ops.testing import Harness

from charm import Oai5GUDROperatorCharm


class TestCharm(unittest.TestCase):
    @patch(
        "charm.KubernetesServicePatch",
        lambda charm, ports: None,
    )
    def setUp(self):
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)
        self.harness = Harness(Oai5GUDROperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch("ops.model.Container.exists")
    def test_given_config_file_is_written_when_pebble_ready_then_pebble_plan_is_created(
        self, mock_container_exists
    ):
        mock_container_exists.return_value = True
        expected_plan = {
            "services": {
                "udr": {
                    "override": "replace",
                    "summary": "udr",
                    "command": "/bin/bash /openair-udr/bin/entrypoint.sh /openair-udr/bin/oai_udr -c /openair-udr/etc/udr.conf -o",  # noqa: E501
                    "startup": "enabled",
                    "environment": {
                        "INSTANCE": "0",
                        "MYSQL_DB": "oai_db",
                        "MYSQL_PASS": "linux",
                        "MYSQL_IPV4_ADDRESS": "mysql",
                        "MYSQL_USER": "root",
                        "NRF_API_VERSION": "v1",
                        "NRF_FQDN": "oai-nrf-svc",
                        "NRF_IPV4_ADDRESS": "127.0.0.1",
                        "NRF_PORT": "80",
                        "PID_DIRECTORY": "/var/run",
                        "REGISTER_NRF": "no",
                        "TZ": "Europe/Paris",
                        "UDR_API_VERSION": "v1",
                        "UDR_INTERFACE_PORT_FOR_NUDR": "80",
                        "UDR_INTERFACE_HTTP2_PORT_FOR_NUDR": "8080",
                        "UDR_INTERFACE_NAME_FOR_NUDR": "eth0",
                        "UDR_NAME": "oai-udr",
                        "USE_FQDN_DNS": "yes",
                        "USE_HTTP2": "no",
                    },
                }
            },
        }
        self.harness.container_pebble_ready("udr")
        updated_plan = self.harness.get_container_pebble_plan("udr").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        service = self.harness.model.unit.get_container("udr").get_service("udr")
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
