#!/usr/bin/env python3
# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Charmed Operator for the OpenAirInterface 5G Core UDR component."""


import logging

from charms.observability_libs.v1.kubernetes_service_patch import (  # type: ignore[import]
    KubernetesServicePatch,
    ServicePort,
)
from jinja2 import Environment, FileSystemLoader
from ops.charm import CharmBase, ConfigChangedEvent, PebbleReadyEvent
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus

logger = logging.getLogger(__name__)

BASE_CONFIG_PATH = "/openair-udr/etc"
CONFIG_FILE_NAME = "udr.conf"


class Oai5GUDROperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Observes juju events."""
        super().__init__(*args)
        self._container_name = "udr"
        self._container = self.unit.get_container(self._container_name)
        self.service_patcher = KubernetesServicePatch(
            charm=self,
            ports=[
                ServicePort(
                    name="http1",
                    port=int(self._config_nudr_interface_port),
                    protocol="TCP",
                    targetPort=int(self._config_nudr_interface_port),
                ),
                ServicePort(
                    name="http2",
                    port=int(self._config_nudr_interface_http2_port),
                    protocol="TCP",
                    targetPort=int(self._config_nudr_interface_http2_port),
                ),
            ],
        )
        self.framework.observe(self.on.udr_pebble_ready, self._on_udr_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_udr_pebble_ready(self, event: PebbleReadyEvent) -> None:
        """Triggered on Pebble Ready Event.

        Args:
            event: Pebble Ready Event

        Returns:
            None
        """
        if not self._config_file_is_pushed:
            self.unit.status = WaitingStatus("Waiting for config files to be pushed")
            event.defer()
            return
        self._container.add_layer("udr", self._pebble_layer, combine=True)
        self._container.replan()
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Triggered on any change in configuration.

        Args:
            event: Config Changed Event

        Returns:
            None
        """
        if not self._container.can_connect():
            self.unit.status = WaitingStatus("Waiting for Pebble in workload container")
            event.defer()
            return
        self._push_config()
        self._container.replan()
        self.unit.status = ActiveStatus()

    def _push_config(self) -> None:
        jinja2_environment = Environment(loader=FileSystemLoader("src/templates/"))
        template = jinja2_environment.get_template(f"{CONFIG_FILE_NAME}.j2")
        content = template.render(
            instance=self._config_instance,
            pid_directory=self._config_pid_directory,
            udr_name=self._config_udr_name,
            use_fqdn_dns=self._config_use_fqdn_dns,
            register_nrf=self._config_register_nrf,
            use_http2=self._config_use_http2,
            nudr_interface_name=self._config_nudr_interface_name,
            nudr_interface_port=self._config_nudr_interface_port,
            nudr_interface_http2_port=self._config_nudr_interface_http2_port,
            nudr_interface_api_version=self._config_nudr_interface_api_version,
            nrf_ipv4_address=self._config_nrf_ipv4_address,
            nrf_port=self._config_nrf_port,
            nrf_api_version=self._config_nrf_api_version,
            nrf_fqdn=self._config_nrf_fqdn,
            mysql_server=self._config_mysql_server,
            mysql_user=self._config_mysql_user,
            mysql_password=self._config_mysql_password,
            mysql_database=self._config_mysql_database,
        )

        self._container.push(path=f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}", source=content)
        logger.info(f"Wrote file to container: {CONFIG_FILE_NAME}")

    @property
    def _config_file_is_pushed(self) -> bool:
        """Check if config file is pushed to the container."""
        if not self._container.exists(f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}"):
            logger.info(f"Config file is not written: {CONFIG_FILE_NAME}")
            return False
        logger.info("Config file is pushed")
        return True

    @property
    def _config_instance(self) -> str:
        return "0"

    @property
    def _config_pid_directory(self) -> str:
        return "/var/run"

    @property
    def _config_udr_name(self) -> str:
        return "oai-udr"

    @property
    def _config_use_fqdn_dns(self) -> str:
        return "yes"

    @property
    def _config_register_nrf(self) -> str:
        return "no"

    @property
    def _config_use_http2(self) -> str:
        return "no"

    @property
    def _config_nrf_ipv4_address(self) -> str:
        return "127.0.0.1"

    @property
    def _config_nrf_port(self) -> str:
        return "80"

    @property
    def _config_nrf_api_version(self) -> str:
        return "v1"

    @property
    def _config_nrf_fqdn(self) -> str:
        return "oai-nrf-svc"

    @property
    def _config_mysql_server(self) -> str:
        return "mysql"

    @property
    def _config_mysql_user(self) -> str:
        return "root"

    @property
    def _config_mysql_password(self) -> str:
        return "linux"

    @property
    def _config_mysql_database(self) -> str:
        return "oai_db"

    @property
    def _config_nudr_interface_name(self) -> str:
        return self.model.config["udrInterfaceNameForNudr"]

    @property
    def _config_nudr_interface_port(self) -> str:
        return "80"

    @property
    def _config_nudr_interface_http2_port(self) -> str:
        return "8080"

    @property
    def _config_nudr_interface_api_version(self) -> str:
        return "v1"

    @property
    def _config_timezone(self) -> str:
        return "Europe/Paris"

    @property
    def _pebble_layer(self) -> dict:
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "udr layer",
            "description": "pebble config layer for udr",
            "services": {
                "udr": {
                    "override": "replace",
                    "summary": "udr",
                    "command": f"/bin/bash /openair-udr/bin/entrypoint.sh /openair-udr/bin/oai_udr -c {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME} -o",  # noqa: E501
                    "startup": "enabled",
                    "environment": {
                        "INSTANCE": self._config_instance,
                        "MYSQL_DB": self._config_mysql_database,
                        "MYSQL_PASS": self._config_mysql_password,
                        "MYSQL_IPV4_ADDRESS": self._config_mysql_server,
                        "MYSQL_USER": self._config_mysql_user,
                        "NRF_API_VERSION": self._config_nrf_api_version,
                        "NRF_FQDN": self._config_nrf_fqdn,
                        "NRF_IPV4_ADDRESS": self._config_nrf_ipv4_address,
                        "NRF_PORT": self._config_nrf_port,
                        "PID_DIRECTORY": self._config_pid_directory,
                        "REGISTER_NRF": self._config_register_nrf,
                        "TZ": self._config_timezone,
                        "UDR_API_VERSION": self._config_nudr_interface_api_version,
                        "UDR_INTERFACE_PORT_FOR_NUDR": self._config_nudr_interface_port,
                        "UDR_INTERFACE_HTTP2_PORT_FOR_NUDR": self._config_nudr_interface_http2_port,  # noqa: E501
                        "UDR_INTERFACE_NAME_FOR_NUDR": self._config_nudr_interface_name,
                        "UDR_NAME": self._config_udr_name,
                        "USE_FQDN_DNS": self._config_use_fqdn_dns,
                        "USE_HTTP2": self._config_use_http2,
                    },
                }
            },
        }


if __name__ == "__main__":
    main(Oai5GUDROperatorCharm)
