from dataclasses import dataclass

from pox.lib.addresses import IPAddr, EthAddr

from swarmsdn.forwarding.prefix import Prefix


class MacTable:
    def __init__(self):
        self.mac_table: dict[EthAddr, int] = {}

    def register_mac(self, mac: EthAddr, port: int):
        self.mac_table[mac] = port

    def get_port(self, mac: EthAddr):
        return self.mac_table[mac]

    def remove(self, mac: EthAddr):
        del self.mac_table[mac]

    def flush(self):
        self.mac_table.clear()


class RouteTable:
    def __init__(self):
        self.entries = {}

    def add_entry(self, prefix: str, intf: str, next_hop: str) -> None:
        """Add forwarding entry mapping prefix to interface and next hop
        IP address."""

        prefix = Prefix(prefix)

        if intf is None:
            intf, next_hop1 = self.get_entry(next_hop)

        self.entries[prefix] = (intf, next_hop)

    def remove_entry(self, prefix: str) -> None:
        """Remove the forwarding entry matching prefix."""

        prefix = Prefix(prefix)

        if prefix in self.entries:
            del self.entries[prefix]

    def flush(self, family: int = None, global_only: bool = True) -> None:
        """Flush the routing table."""

        routes = self.get_all_entries(family=family, resolve=False, global_only=global_only)

        for prefix in routes:
            del self.entries[prefix]

    def get_entry(self, address: str) -> tuple[str, str]:
        """Return the subnet entry having the longest prefix match of
        address.  The entry is a tuple consisting of interface and
        next-hop IP address.  If there is no match, return None, None."""

        max_length = -1
        max_length_entry = None
        for entry in self.entries:
            if address in entry and entry.prefix_len > max_length:
                max_length_entry = entry
                max_length = entry.prefix_len

        if max_length_entry is not None:
            return self.entries[max_length_entry]

        return None, None

    def get_all_entries(self, family: int = None, resolve: bool = False, global_only: bool = True):
        entries = {}
        for prefix in self.entries:
            intf, next_hop = self.entries[prefix]
            if next_hop is not None or not global_only:
                entries[prefix] = (intf, next_hop)
        return entries
