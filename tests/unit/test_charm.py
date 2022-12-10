# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import ops.testing
from ops.model import ActiveStatus
from ops.pebble import ServiceInfo, ServiceStartup, ServiceStatus
from ops.testing import Harness

from charm import Oai5GUDROperatorCharm


class TestCharm(unittest.TestCase):
    @patch(
        "charm.KubernetesServicePatch",
        lambda charm, ports: None,
    )
    def setUp(self):
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.model_name = "whatever"
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)
        self.harness = Harness(Oai5GUDROperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.set_model_name(name=self.model_name)
        self.harness.begin()

    def _create_nrf_relation_with_valid_data(self):
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
        return nrf_ipv4_address, nrf_port, nrf_api_version, nrf_fqdn

    def _create_database_relation_with_valid_data(self):
        relation_id = self.harness.add_relation(relation_name="database", remote_app="mysql")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="mysql/0")
        username = "whatever username"
        password = "whatever password"
        endpoints = "whatever endpoint 1,whatever endpoint 2"
        key_values = {
            "username": username,
            "password": password,
            "endpoints": endpoints,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="mysql", key_values=key_values
        )
        return username, password, endpoints

    @patch("ops.model.Container.push")
    def test_given_nrf_relation_contains_nrf_info_when_nrf_relation_joined_then_config_file_is_pushed(  # noqa: E501
        self, mock_push
    ):
        self.harness.set_can_connect(container="udr", val=True)

        username, password, endpoints = self._create_database_relation_with_valid_data()
        (
            nrf_ipv4_address,
            nrf_port,
            nrf_api_version,
            nrf_fqdn,
        ) = self._create_nrf_relation_with_valid_data()

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
            f'    MYSQL_SERVER = "{ endpoints.split(",")[0] }";\n'
            f'    MYSQL_USER   = "{ username }";\n'
            f'    MYSQL_PASS   = "{ password }";\n'
            '    MYSQL_DB     = "oai_db";\n'
            "    DB_CONNECTION_TIMEOUT = 300;           # Reset the connection to the DB after expiring the timeout (in second)\n"  # noqa: E501, W505
            "  };\n"
            "};",
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_and_db_relation_are_set_when_config_changed_then_pebble_plan_is_created(  # noqa: E501
        self, _
    ):
        self._create_database_relation_with_valid_data()
        self._create_nrf_relation_with_valid_data()

        self.harness.update_config({"udrInterfaceNameForNudr": "eth0"})

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

    @patch("ops.model.Container.get_service")
    def test_given_unit_is_leader_when_nrf_relation_joined_then_udr_relation_data_is_set(
        self, patch_get_service
    ):
        self.harness.set_leader(True)
        self.harness.set_can_connect(container="udr", val=True)
        patch_get_service.return_value = ServiceInfo(
            name="udr",
            current=ServiceStatus.ACTIVE,
            startup=ServiceStartup.ENABLED,
        )

        relation_id = self.harness.add_relation(relation_name="fiveg-udr", remote_app="udm")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="udm/0")

        relation_data = self.harness.get_relation_data(
            relation_id=relation_id, app_or_unit=self.harness.model.app.name
        )

        assert relation_data["udr_ipv4_address"] == "127.0.0.1"
        assert relation_data["udr_fqdn"] == f"oai-5g-udr.{self.model_name}.svc.cluster.local"
        assert relation_data["udr_port"] == "80"
        assert relation_data["udr_api_version"] == "v1"
