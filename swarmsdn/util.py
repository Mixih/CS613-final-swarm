from dataclasses import dataclass, field
from typing import Any

from pox.lib.addresses import EthAddr, IPAddr


@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)


def dpid_to_mac(dpid: int):
    return EthAddr(f"02:00:00:00:ff:{dpid:02x}")


def host_ip_to_mac(ip_addr: IPAddr):
    host_no = ip_addr.toUnsigned() & 0xFF
    return EthAddr(f"02:00:00:00:ff:{host_no:02x}")
