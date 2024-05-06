from dataclasses import dataclass
from enum import Enum

from pox.lib.addresses import EthAddr, IPAddr
from pox.lib.packet.ethernet import ethernet


@dataclass
class InPacketMeta:
    iport: int
    smac: EthAddr
    dmac: EthAddr
    src_ip: IPAddr
    dst_ip: IPAddr
    ethtype: int
    pkt: ethernet


class InPacketType(Enum):
    ARP = 0
    IPV4 = 1
