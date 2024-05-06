from pox.core import core
from pox.openflow.of_01 import ConnectionUp, PacketIn
from pox.lib.revent import EventMixin
from pox.openflow.discovery import LinkEvent
from pox.lib.util import dpid_to_str
from pox.lib.packet.arp import arp
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.ethernet import ethernet
import pox.openflow.libopenflow_01 as of
from pox.openflow.of_01 import Connection
from pox.lib.addresses import EthAddr

from swarmsdn.graph import NetGraph
from swarmsdn.table import MacTable
from swarmsdn.openflow import InPacketMeta, InPacketType

log = core.getLogger()


class GraphControllerBase(EventMixin):
    """
    Invariant: switches always are directly connected to nodes in route
    10.0.<dpid_as_int>.0

    To make changes use self.l2routes[<dpid>] methods
    """

    ENTRY_TIMEOUT = 5
    PRI_FWD = 1

    def __init__(self, debug: bool = False):
        self.listenTo(core.openflow)
        self.listenTo(core.openflow_discovery)
        core.openflow_discovery.addListeners(self)

        self.debug = debug
        self.graph = NetGraph()  # clear manually!
        self.graph_updated = False
        self.l2routes: dict[int, MacTable] = {}

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

    def clear_of_tables_for_switch(self, dpid: int):
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
            dst_ip = next_header.protodst
        else:
            log.debug(
                "Unhandled next packet type " f"{pkt.getNameForType(pkt.effective_ethertype)}"
            )
            raise KeyError("Bad Packet Type.")
        return (
            InPacketMeta(
                iport=event.port,
                smac=pkt.src,
                dmac=pkt.dst,
                src_ip=src_ip,
                dst_ip=dst_ip,
                ethtype=pkt.effective_ethertype,
                pkt=pkt,
            ),
            pkt_type,
        )

    def _disable_flood_on_port(self, conn: Connection, port_no: int):
        p: of.ofp_phy_port = conn.ports[1]
        msg = of.ofp_port_mod(
            port_no=p.port_no, hw_addr=p.hw_addr, config=of.OFPPC_NO_FLOOD, mask=of.OFPPC_NO_FLOOD
        )
        conn.send(msg)

    def _flood(self, connection: Connection, pkt_info: InPacketMeta):
        msg = of.ofp_packet_out()
        msg.in_port = pkt_info.iport
        msg.data = pkt_info.pkt.pack()
        # OFPP_FLOOD: output all openflow ports expect the input port and those with
        #    flooding disabled via the OFPPC_NO_FLOOD port config bit
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        log.debug("Unknown swdport for dmac on DPID, flooding packet to all ports.")
        connection.send(msg)

    def _install_fwd_rule(self, connection: Connection, pkt_info: InPacketMeta, dport: int):
        # queue up flow table addition
        match = of.ofp_match(
            in_port=pkt_info.iport,
            dl_src=pkt_info.smac,
            dl_dst=pkt_info.dmac,
            dl_type=pkt_info.ethtype,
        )
        msg = of.ofp_flow_mod(
            command=of.OFPFC_ADD,
            idle_timeout=self.ENTRY_TIMEOUT,
            priority=self.PRI_FWD,
            match=match,
        )
        msg.actions.append(of.ofp_action_output(port=dport))
        connection.send(msg)
        # queue up the original packet so we don't drop it
        msg = of.ofp_packet_out(in_port=pkt_info.iport, data=pkt_info.pkt.pack())
        msg.actions.append(of.ofp_action_output(port=of.OFPP_TABLE))
        connection.send(msg)

    def _handle_arp(self, connection: Connection, pkt_info: InPacketMeta):
        pass

    def _handle_PacketIn(self, event: PacketIn):
        log.debug("############ NEW PACKET IN EVT ############")

        dpid: int = event.dpid
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

        dport = self.mac_routes[dpid].fwd_table.get_port(pkt_info.dmac)

        # learn mac mapping for directly connected nodes only
        if self.l2routes[dpid].get_port(pkt_info.smac) is None and pkt_info.smac != EthAddr(
            "ff:ff:ff:ff:ff:ff"
        ):
            self.l2routes[dpid].register_mac(pkt_info.smac, pkt_info.iport)

        # the controller can directly resolve arp requests using some invariants
        if pkt_type == InPacketType.ARP:
            self._handle_arp(event.connection, pkt_info)
        else:
            # if we have a route, add the rule and send it
            if dport is not None:
                self._install_fwd_rule(event.connection, pkt_info, dport)
            # otherwise flood it to local nodes
            else:
                self._flood(event.connection, pkt_info)
        # if neither work, that means we didn't have a route and the packet dies

    def _handle_LinkEvent(self, event: LinkEvent):
        # test that discovery works
        if self.debug:
            log.debug("======LINK EVT========")
        self.graph.update_from_linkevent(event)
        self.graph_updated = True
        # discovered connections are EXTERNAL between switches and should not accept arp
        # flood
        if event.added:
            self._disable_flood_on_port(
                core.openflow.getConnection(event.link.dpid1), event.link.port1
            )
            self._disable_flood_on_port(
                core.openflow.getConnection(event.link.dpid2), event.link.port2
            )
        self.hook_handle_link_event(event)

    def _handle_ConnectionUp(self, event: ConnectionUp):
        if self.debug:
            log.debug("=========== SW UP EVT ===========")
        self.graph.register_node(event.dpid)
        self.l2routes[event.dpid] = MacTable()
        self.hook_handle_connetion_up(event)
