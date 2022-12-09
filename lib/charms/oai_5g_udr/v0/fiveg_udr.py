# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G UDR."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "ea8425a6bb8642c3be3666a457964369"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 2


logger = logging.getLogger(__name__)


class UDRAvailableEvent(EventBase):
    """Charm event emitted when an UDR is available."""

    def __init__(
        self,
        handle: Handle,
        udr_ipv4_address: str,
        udr_fqdn: str,
        udr_port: str,
        udr_api_version: str,
    ):
        """Init."""
        super().__init__(handle)
        self.udr_ipv4_address = udr_ipv4_address
        self.udr_fqdn = udr_fqdn
        self.udr_port = udr_port
        self.udr_api_version = udr_api_version

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "udr_ipv4_address": self.udr_ipv4_address,
            "udr_fqdn": self.udr_fqdn,
            "udr_port": self.udr_port,
            "udr_api_version": self.udr_api_version,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.udr_ipv4_address = snapshot["udr_ipv4_address"]
        self.udr_fqdn = snapshot["udr_fqdn"]
        self.udr_port = snapshot["udr_port"]
        self.udr_api_version = snapshot["udr_api_version"]


class FiveGUDRRequirerCharmEvents(CharmEvents):
    """List of events that the 5G UDR requirer charm can leverage."""

    udr_available = EventSource(UDRAvailableEvent)


class FiveGUDRRequires(Object):
    """Class to be instantiated by the charm requiring the 5G UDR Interface."""

    on = FiveGUDRRequirerCharmEvents()

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
        if "udr_ipv4_address" not in remote_app_relation_data:
            logger.info(
                "No udr_ipv4_address in relation data - Not triggering udr_available event"
            )
            return
        if "udr_fqdn" not in remote_app_relation_data:
            logger.info("No udr_fqdn in relation data - Not triggering udr_available event")
            return
        if "udr_port" not in remote_app_relation_data:
            logger.info("No udr_port in relation data - Not triggering udr_available event")
            return
        if "udr_api_version" not in remote_app_relation_data:
            logger.info("No udr_api_version in relation data - Not triggering udr_available event")
            return
        self.on.udr_available.emit(
            udr_ipv4_address=remote_app_relation_data["udr_ipv4_address"],
            udr_fqdn=remote_app_relation_data["udr_fqdn"],
            udr_port=remote_app_relation_data["udr_port"],
            udr_api_version=remote_app_relation_data["udr_api_version"],
        )

    @property
    def udr_ipv4_address_available(self) -> bool:
        """Returns whether udr address is available in relation data."""
        if self.udr_ipv4_address:
            return True
        else:
            return False

    @property
    def udr_ipv4_address(self) -> Optional[str]:
        """Returns udr_ipv4_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udr_ipv4_address", None)

    @property
    def udr_fqdn_available(self) -> bool:
        """Returns whether udr fqdn is available in relation data."""
        if self.udr_fqdn:
            return True
        else:
            return False

    @property
    def udr_fqdn(self) -> Optional[str]:
        """Returns udr_fqdn from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udr_fqdn", None)

    @property
    def udr_port_available(self) -> bool:
        """Returns whether udr port is available in relation data."""
        if self.udr_port:
            return True
        else:
            return False

    @property
    def udr_port(self) -> Optional[str]:
        """Returns udr_port from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udr_port", None)

    @property
    def udr_api_version_available(self) -> bool:
        """Returns whether udr api version is available in relation data."""
        if self.udr_api_version:
            return True
        else:
            return False

    @property
    def udr_api_version(self) -> Optional[str]:
        """Returns udr_api_version from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udr_api_version", None)


class FiveGUDRProvides(Object):
    """Class to be instantiated by the UDR charm providing the 5G UDR Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_udr_information(
        self,
        udr_ipv4_address: str,
        udr_fqdn: str,
        udr_port: str,
        udr_api_version: str,
        relation_id: int,
    ) -> None:
        """Sets UDR information in relation data.

        Args:
            udr_ipv4_address: UDR address
            udr_fqdn: UDR FQDN
            udr_port: UDR port
            udr_api_version: UDR API version
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "udr_ipv4_address": udr_ipv4_address,
                "udr_fqdn": udr_fqdn,
                "udr_port": udr_port,
                "udr_api_version": udr_api_version,
            }
        )
