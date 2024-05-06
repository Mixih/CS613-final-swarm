from dataclasses import dataclass
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet.ethernet import ethernet

from enum import Enum


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
