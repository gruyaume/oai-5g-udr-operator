# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G NRF."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "491530841b444e289ba34d2e948e5669"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 3


logger = logging.getLogger(__name__)


class NRFAvailableEvent(EventBase):
    """Charm event emitted when an NRF is available."""

    def __init__(
        self,
        handle: Handle,
        nrf_ipv4_address: str,
        nrf_fqdn: str,
        nrf_port: str,
        nrf_api_version: str,
    ):
        """Init."""
        super().__init__(handle)
        self.nrf_ipv4_address = nrf_ipv4_address
        self.nrf_fqdn = nrf_fqdn
        self.nrf_port = nrf_port
        self.nrf_api_version = nrf_api_version

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "nrf_ipv4_address": self.nrf_ipv4_address,
            "nrf_fqdn": self.nrf_fqdn,
            "nrf_port": self.nrf_port,
            "nrf_api_version": self.nrf_api_version,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.nrf_ipv4_address = snapshot["nrf_ipv4_address"]
        self.nrf_fqdn = snapshot["nrf_fqdn"]
        self.nrf_port = snapshot["nrf_port"]
        self.nrf_api_version = snapshot["nrf_api_version"]


class FiveGNRFRequirerCharmEvents(CharmEvents):
    """List of events that the 5G NRF requirer charm can leverage."""

    nrf_available = EventSource(NRFAvailableEvent)


class FiveGNRFRequires(Object):
    """Class to be instantiated by the charm requiring the 5G NRF Interface."""

    on = FiveGNRFRequirerCharmEvents()

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.charm = charm
        self.relationship_name = relationship_name
        self.framework.observe(
            charm.on[relationship_name].relation_changed, self._on_relation_changed
        )

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handler triggered on relation changed event.

        Args:
            event: Juju event (RelationChangedEvent)

        Returns:
            None
        """
        relation = event.relation
        if not relation.app:
            logger.warning("No remote application in relation: %s", self.relationship_name)
            return
        remote_app_relation_data = relation.data[relation.app]
        if "nrf_ipv4_address" not in remote_app_relation_data:
            logger.info(
                "No nrf_ipv4_address in relation data - Not triggering nrf_available event"
            )
            return
        if "nrf_fqdn" not in remote_app_relation_data:
            logger.info("No nrf_fqdn in relation data - Not triggering nrf_available event")
            return
        if "nrf_port" not in remote_app_relation_data:
            logger.info("No nrf_port in relation data - Not triggering nrf_available event")
            return
        if "nrf_api_version" not in remote_app_relation_data:
            logger.info("No nrf_api_version in relation data - Not triggering nrf_available event")
            return
        self.on.nrf_available.emit(
            nrf_ipv4_address=remote_app_relation_data["nrf_ipv4_address"],
            nrf_fqdn=remote_app_relation_data["nrf_fqdn"],
            nrf_port=remote_app_relation_data["nrf_port"],
            nrf_api_version=remote_app_relation_data["nrf_api_version"],
        )

    @property
    def nrf_ipv4_address_available(self) -> bool:
        """Returns whether nrf address is available in relation data."""
        if self.nrf_ipv4_address:
            return True
        else:
            return False

    @property
    def nrf_ipv4_address(self) -> Optional[str]:
        """Returns nrf_ipv4_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("nrf_ipv4_address", None)

    @property
    def nrf_fqdn_available(self) -> bool:
        """Returns whether nrf fqdn is available in relation data."""
        if self.nrf_fqdn:
            return True
        else:
            return False

    @property
    def nrf_fqdn(self) -> Optional[str]:
        """Returns nrf_fqdn from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("nrf_fqdn", None)

    @property
    def nrf_port_available(self) -> bool:
        """Returns whether nrf port is available in relation data."""
        if self.nrf_port:
            return True
        else:
            return False

    @property
    def nrf_port(self) -> Optional[str]:
        """Returns nrf_port from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("nrf_port", None)

    @property
    def nrf_api_version_available(self) -> bool:
        """Returns whether nrf api version is available in relation data."""
        if self.nrf_api_version:
            return True
        else:
            return False

    @property
    def nrf_api_version(self) -> Optional[str]:
        """Returns nrf_api_version from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("nrf_api_version", None)


class FiveGNRFProvides(Object):
    """Class to be instantiated by the NRF charm providing the 5G NRF Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_nrf_information(
        self,
        nrf_ipv4_address: str,
        nrf_fqdn: str,
        nrf_port: str,
        nrf_api_version: str,
        relation_id: int,
    ) -> None:
        """Sets NRF information in relation data.

        Args:
            nrf_ipv4_address: NRF address
            nrf_fqdn: NRF FQDN
            nrf_port: NRF port
            nrf_api_version: NRF API version
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "nrf_ipv4_address": nrf_ipv4_address,
                "nrf_fqdn": nrf_fqdn,
                "nrf_port": nrf_port,
                "nrf_api_version": nrf_api_version,
            }
        )
