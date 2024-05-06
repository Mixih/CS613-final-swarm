from pox.lib.addresses import EthAddr


class MacTable:
    def __init__(self):
        self.mac_table: dict[EthAddr, int] = {}
        self.reverse_map: dict[int, set[EthAddr]] = {}

    def register_mac(self, mac: EthAddr, port: int):
        self.mac_table[mac] = port
        if port not in self.reverse_map:
            self.reverse_map[port] = set()
        self.reverse_map[port].add(mac)

    def get_port(self, mac: EthAddr):
        if mac in self.mac_table:
            return self.mac_table[mac]
        return None

    def get_macs_by_port(self, port: int) -> set[EthAddr]:
        if port in self.reverse_map:
            return self.reverse_map[port]
        return set()

    def remove(self, mac: EthAddr):
        port = self.mac_table[mac]
        del self.mac_table[mac]
        self.reverse_map[port].remove(mac)

    def flush(self):
        self.mac_table.clear()
        self.reverse_map.clear()
