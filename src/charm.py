#!/usr/bin/env python3
# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Charmed Operator for the OpenAirInterface 5G Core UDR component."""


import logging

from charms.data_platform_libs.v0.database_requires import (  # type: ignore[import]
    DatabaseRequires,
)
from charms.oai_5g_nrf.v0.fiveg_nrf import FiveGNRFRequires  # type: ignore[import]
from charms.oai_5g_udr.v0.fiveg_udr import FiveGUDRProvides  # type: ignore[import]
from charms.observability_libs.v1.kubernetes_service_patch import (  # type: ignore[import]
    KubernetesServicePatch,
    ServicePort,
)
from jinja2 import Environment, FileSystemLoader
from ops.charm import CharmBase, ConfigChangedEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, ModelError, WaitingStatus

logger = logging.getLogger(__name__)

BASE_CONFIG_PATH = "/openair-udr/etc"
CONFIG_FILE_NAME = "udr.conf"
DATABASE_NAME = "oai_db"


class Oai5GUDROperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Observes juju events."""
        super().__init__(*args)
        self._container_name = self._service_name = "udr"
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
        self.udr_provides = FiveGUDRProvides(self, "fiveg-udr")
        self.nrf_requires = FiveGNRFRequires(self, "fiveg-nrf")
        self.database = DatabaseRequires(
            self, relation_name="database", database_name=DATABASE_NAME
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fiveg_nrf_relation_changed, self._on_config_changed)
        self.framework.observe(self.database.on.database_created, self._on_config_changed)
        self.framework.observe(
            self.on.fiveg_udr_relation_joined, self._on_fiveg_udr_relation_joined
        )

    def _on_fiveg_udr_relation_joined(self, event) -> None:
        """Triggered when a relation is joined.

        Args:
            event: Relation Joined Event
        """
        if not self.unit.is_leader():
            return
        if not self._udr_service_started:
            logger.info("UDR service not started yet, deferring event")
            event.defer()
            return
        self.udr_provides.set_udr_information(
            udr_ipv4_address="127.0.0.1",
            udr_fqdn=f"{self.model.app.name}.{self.model.name}.svc.cluster.local",
            udr_port=self._config_nudr_interface_port,
            udr_api_version=self._config_nudr_interface_api_version,
            relation_id=event.relation.id,
        )

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
        if not self._database_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to database to be created")
            return
        if not self._nrf_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to NRF to be created")
            return
        if not self._database_relation_data_is_available:
            self.unit.status = WaitingStatus("Waiting for database relation data to be available")
            return
        if not self.nrf_requires.nrf_ipv4_address_available:
            self.unit.status = WaitingStatus(
                "Waiting for NRF IPv4 address to be available in relation data"
            )
            return
        self._push_config()
        self._update_pebble_layer()
        if self.unit.is_leader():
            self._set_udr_information_for_all_relations()
        self.unit.status = ActiveStatus()

    def _set_udr_information_for_all_relations(self):
        self.udr_provides.set_udr_information_for_all_relations(
            udr_ipv4_address="127.0.0.1",
            udr_fqdn=f"{self.model.app.name}.{self.model.name}.svc.cluster.local",
            udr_port=self._config_nudr_interface_port,
            udr_api_version=self._config_nudr_interface_api_version,
        )

    @property
    def _database_relation_data_is_available(self) -> bool:
        relation_data = self.database.fetch_relation_data()
        if not relation_data:
            return False
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            return False
        if "username" not in relation_data[relation.id]:
            return False
        if "password" not in relation_data[relation.id]:
            return False
        if "endpoints" not in relation_data[relation.id]:
            return False
        return True

    def _update_pebble_layer(self) -> None:
        """Updates pebble layer with new configuration.

        Returns:
            None
        """
        self._container.add_layer("udr", self._pebble_layer, combine=True)
        self._container.replan()
        self._container.restart(self._service_name)

    @property
    def _udr_service_started(self) -> bool:
        if not self._container.can_connect():
            return False
        try:
            service = self._container.get_service(self._service_name)
        except ModelError:
            return False
        if not service.is_running():
            return False
        return True

    @property
    def _nrf_relation_created(self) -> bool:
        return self._relation_created("fiveg-nrf")

    @property
    def _database_relation_created(self) -> bool:
        return self._relation_created("database")

    def _relation_created(self, relation_name: str) -> bool:
        if not self.model.get_relation(relation_name):
            return False
        return True

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
            nrf_ipv4_address=self.nrf_requires.nrf_ipv4_address,
            nrf_port=self.nrf_requires.nrf_port,
            nrf_api_version=self.nrf_requires.nrf_api_version,
            nrf_fqdn=self.nrf_requires.nrf_fqdn,
            mysql_server=self._database_relation_server,
            mysql_user=self._database_relation_user,
            mysql_password=self._database_relation_password,
            mysql_database=DATABASE_NAME,
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
    def _database_relation_server(self) -> str:
        relation_data = self.database.fetch_relation_data()
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            raise ValueError("Database relation is not created")
        return relation_data[relation.id]["endpoints"].split(",")[0].split(":")[0]

    @property
    def _database_relation_user(self) -> str:
        relation_data = self.database.fetch_relation_data()
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            raise ValueError("Database relation is not created")
        return relation_data[relation.id]["username"]

    @property
    def _database_relation_password(self) -> str:
        relation_data = self.database.fetch_relation_data()
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            raise ValueError("Database relation is not created")
        return relation_data[relation.id]["password"]

    @property
    def _config_nudr_interface_name(self) -> str:
        return "eth0"

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
    def _pebble_layer(self) -> dict:
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "udr layer",
            "description": "pebble config layer for udr",
            "services": {
                self._service_name: {
                    "override": "replace",
                    "summary": "udr",
                    "command": f"/bin/bash /openair-udr/bin/entrypoint.sh /openair-udr/bin/oai_udr -c {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME} -o",  # noqa: E501
                    "startup": "enabled",
                }
            },
        }


if __name__ == "__main__":
    main(Oai5GUDROperatorCharm)
