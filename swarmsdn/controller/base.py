from pox.core import core
from pox.openflow.of_01 import ConnectionUp, PacketIn
from pox.lib.revent import EventMixin
from pox.openflow.discovery import LinkEvent
from pox.lib.util import dpid_to_str
from pox.lib.packet.arp import arp
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.ethernet import ethernet
import pox.openflow.libopenflow_01 as of

from swarmsdn.graph import NetGraph
from swarmsdn.switch import SwitchMeta
from swarmsdn.openflow import InPacketMeta, InPacketType

log = core.getLogger()


class GraphControllerBase(EventMixin):
    """
    Invariant: switches always are directly connected to nodes in route
    10.0.<dpid_as_int>.0

    To make routing changes, update self.switches[dpid_as_int].routing_table
    The PacketIn handler will handle updating everything else.

    If you flush the routing table for a switch, you either will have to emit openflow messages to
    modify the switch's table in place, or call self.clear_tables_for_switch(<dpid>)
    """

    def __init__(self, debug: bool = False):
        self.listenTo(core.openflow)
        self.listenTo(core.openflow_discovery)
        core.openflow_discovery.addListeners(self)

        self.debug = debug
        self.graph = NetGraph()  # clear manually!
        self.graph_updated = False
        self.switches: dict[int, SwitchMeta] = {}

    def hook_connetion_up(self, event: ConnectionUp) -> None:
        """
        Override in child classes to implement additional connection up behaviour
        """
        pass

    def hook_link_event(self, event: LinkEvent) -> None:
        """
        Override in child classes to implement additional link event behaviour
        """
        pass

    def hook_packet_in_prerouting(self, pkt_info: InPacketMeta, packet_type: InPacketType) -> bool:
        """
        Override in child classes to carry out tasks that should happen before routing
        decisions are made. (e.g. lazy routing table updates). Return False if the rest of
        the default packet in handler should not be run, otherwise return True.
        """
        pass

    def hook_packet_in_postrouting(self, event: PacketIn) -> None:
        """
        Override in child classes to carry out tasks that should happen after routing
        decisions are made.
        """
        pass

    def clear_all_of_tables(self):
        msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
        for connection in core.openflow.connections:
            connection.send(msg)

    def clear_tables_for_switch(self, dpid: int):
        msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
        core.openflow.connections[dpid].send(msg)

    def _parse_packet_from_event(self, event: PacketIn) -> tuple[InPacketMeta, InPacketType]:
        pkt = event.parsed
        src_ip = None
        dst_ip = None
        pkt_type = None
        if pkt.effective_ethertype == ethernet.IP_TYPE:
            pkt_type = InPacketType.IPV4
            next_header: ipv4 = pkt.next
            src_ip = next_header.srcip
            dst_ip = next_header.dstip
        elif pkt.effective_ethertype == ethernet.ARP_TYPE:
            pkt_type = InPacketType.ARP
            next_header: arp = pkt.next
            src_ip = next_header.protosrc
        else:
            log.debug(
                "Unhandled next packet type " f"{pkt.getNameForType(pkt.effective_ethertype)}"
            )
            raise KeyError("Bad Packet Type.")
        return (
            InPacketMeta(
                iport=event.port, smac=pkt.src, dmac=pkt.dst, src_ip=src_ip, dst_ip=dst_ip, pkt=pkt
            ),
            pkt_type,
        )

    def route_arp(self, pkt_info: InPacketMeta):
        pass

    def route_ip(self, pkt_info: InPacketMeta):
        pass

    def _handle_PacketIn(self, event: PacketIn):
        log.debug("############ NEW PACKET IN EVT ############")

        dpid: str = dpid_to_str(event.dpid)
        pkt_info, pkt_type = self._parse_packet_from_event(event)

        log.debug(
            f"Got packet from switch {dpid_to_str(dpid)}, port {pkt_info.iport} "
            f"ethertype {pkt_type} "
            f"smac {pkt_info.smac} dmac {pkt_info.dmac} src_ip {pkt_info.src_ip} "
            f"dst_ip: {pkt_info.dst_ip}"
        )
        # call user hook
        if not self.hook_packet_in_prerouting(pkt_info, pkt_type):
            return
        # dispatch to packet routing handler
        if pkt_type == InPacketType.ARP:
            self.route_arp(pkt_info)
        elif pkt_type == InPacketType.IPV4:
            self.route_ip(pkt_info)
        self.hook_packet_in_postrouting()

    def _handle_LinkEvent(self, event: LinkEvent):
        # test that discovery works
        if self.debug:
            log.debug("======LINK EVT========")
        self.graph.update_from_linkevent(event)
        self.graph_updated = True
        self.hook_handle_link_event(event)

    def _handle_ConnectionUp(self, event: ConnectionUp):
        if self.debug:
            log.debug("=========== SW UP EVT ===========")
        self.graph.register_node(event.dpid)
        self.hook_handle_connetion_up(event)
