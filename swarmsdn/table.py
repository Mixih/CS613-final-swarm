from pox.lib.addresses import EthAddr


class MacTable:
    def __init__(self):
        self.mac_table: dict[EthAddr, int] = {}

    def register_mac(self, mac: EthAddr, port: int):
        self.mac_table[mac] = port

    def get_port(self, mac: EthAddr):
        if mac in self.mac_table:
            return self.mac_table[mac]
        return None

    def remove(self, mac: EthAddr):
        del self.mac_table[mac]

    def flush(self):
        self.mac_table.clear()
