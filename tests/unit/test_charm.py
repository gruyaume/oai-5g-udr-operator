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

    @patch("ops.model.Container.push")
    def test_given_nrf_relation_contains_nrf_info_when_nrf_relation_joined_then_config_file_is_pushed(  # noqa: E501
        self, mock_push
    ):
        self.harness.set_can_connect(container="udr", val=True)
        relation_id = self.harness.add_relation("fiveg-nrf", "nrf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="nrf/0")

        nrf_ipv4_address = "1.2.3.4"
        nrf_port = "81"
        nrf_api_version = "v1"
        nrf_fqdn = "nrf.example.com"
        key_values = {
            "nrf_ipv4_address": nrf_ipv4_address,
            "nrf_port": nrf_port,
            "nrf_fqdn": nrf_fqdn,
            "nrf_api_version": nrf_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="nrf", key_values=key_values
        )

        mock_push.assert_called_with(
            path="/openair-udr/etc/udr.conf",
            source="UDR =\n"
            "{\n"
            "  INSTANCE_ID = 0;            # 0 is the default\n"
            '  PID_DIRECTORY = "/var/run";   # /var/run is the default\n'
            '  UDR_NAME = "oai-udr";\n\n\n'
            "  SUPPORT_FEATURES:{\n"
            '    USE_FQDN_DNS = "yes";    # Set to yes if UDR will relying on a DNS to resolve UDM\'s FQDN\n'  # noqa: E501, W505
            '    REGISTER_NRF = "no";    # Set to yes if UDR resgisters to an NRF\n'
            '    USE_HTTP2    = "no";       # Set to yes to enable HTTP2 for UDR server\n'
            "    DATABASE     = \"MySQL\";             # Set to 'MySQL'/'Cassandra' to use MySQL/Cassandra\n  };\n\n"  # noqa: E501, W505
            "  INTERFACES:\n"
            "  {\n"
            "    # NUDR Interface (SBI)\n"
            "    NUDR:\n"
            "    {\n"
            '      INTERFACE_NAME = "eth0";\n'
            '      IPV4_ADDRESS   = "read";\n'
            "      PORT           = 80;         # Default value: 80\n"
            "      HTTP2_PORT     = 8080;   # Default value: 443\n"
            '      API_VERSION    = "v1";\n'
            "    };\n"
            "  };\n\n"
            "  NRF:\n"
            "  {\n"
            f'    IPV4_ADDRESS = "{ nrf_ipv4_address }";\n'
            f"    PORT         = { nrf_port };            # Default value: 80\n"
            f'    API_VERSION  = "{ nrf_api_version }";\n'
            f'    FQDN         = "{ nrf_fqdn }";\n'
            "  };\n\n"
            "  MYSQL:\n"
            "  {\n"
            "    # MySQL options\n"
            '    MYSQL_SERVER = "mysql";\n'
            '    MYSQL_USER   = "root";\n'
            '    MYSQL_PASS   = "linux";\n'
            '    MYSQL_DB     = "oai_db";\n'
            "    DB_CONNECTION_TIMEOUT = 300;           # Reset the connection to the DB after expiring the timeout (in second)\n"  # noqa: E501, W505
            "  };\n"
            "};",
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_relation_contains_nrf_info_when_nrf_relation_joined_then_pebble_plan_is_created(  # noqa: E501
        self, _
    ):
        self.harness.set_can_connect(container="udr", val=True)
        relation_id = self.harness.add_relation("fiveg-nrf", "nrf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="nrf/0")

        nrf_ipv4_address = "1.2.3.4"
        key_values = {
            "nrf_ipv4_address": nrf_ipv4_address,
            "nrf_port": "80",
            "nrf_fqdn": "nrf.example.com",
            "nrf_api_version": "v1",
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="nrf", key_values=key_values
        )

        expected_plan = {
            "services": {
                "udr": {
                    "override": "replace",
                    "summary": "udr",
                    "command": "/bin/bash /openair-udr/bin/entrypoint.sh /openair-udr/bin/oai_udr -c /openair-udr/etc/udr.conf -o",  # noqa: E501
                    "startup": "enabled",
                }
            },
        }
        self.harness.container_pebble_ready("udr")
        updated_plan = self.harness.get_container_pebble_plan("udr").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        service = self.harness.model.unit.get_container("udr").get_service("udr")
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
