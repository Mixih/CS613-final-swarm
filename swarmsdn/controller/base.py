import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.addresses import EthAddr
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.revent import EventMixin
from pox.lib.util import dpid_to_str
from pox.openflow.discovery import LinkEvent
from pox.openflow.of_01 import Connection, ConnectionUp, PacketIn
from swarmsdn.graph import NetGraphBidir
from swarmsdn.openflow import InPacketMeta, InPacketType
from swarmsdn.table import MacTable
from swarmsdn.util import host_ip_to_mac

log = core.getLogger()


class GraphControllerBase(EventMixin):
    """
    Invariant: switches always are directly connected to nodes in route
    10.0.<dpid_as_int>.0

    To make changes use self.l2routes[<dpid>] methods
    """

    ENTRY_TIMEOUT = 120
    PRI_FWD = 1

    def __init__(self, debug: bool = False):
        self.listenTo(core.openflow)
        self.listenTo(core.openflow_discovery)
        core.openflow_discovery.addListeners(self)

        self.debug = debug
        self.graph = NetGraphBidir()
        self.graph_updated = False
        self.l2routes: dict[int, MacTable] = {}

    def hook_connection_up(self, event: ConnectionUp) -> None:
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
        return True

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
        core.openflow.getConnection(dpid).send(msg)

    def _set_port_flood_mode(self, dpid: int, port_no: int, flood: bool):
        conn = core.openflow.getConnection(dpid)
        if conn is None or port_no not in conn.ports:
            return
        p: of.ofp_phy_port = conn.ports[port_no]
        msg = of.ofp_port_mod(
            port_no=p.port_no,
            hw_addr=p.hw_addr,
            config=0 if flood else of.OFPPC_NO_FLOOD,
            mask=of.OFPPC_NO_FLOOD,
        )
        conn.send(msg)

    def _clear_rules_for_port(self, dpid: int, port: int):
        conn = core.openflow.getConnection(dpid)
        if conn is None:
            return
        msg = of.ofp_flow_mod(match=of.ofp_match(in_port=port), command=of.OFPFC_DELETE)
        conn.send(msg)
        for mac in self.l2routes[dpid].get_macs_by_port(port):
            msg = of.ofp_flow_mod(match=of.ofp_match(dl_dst=mac), command=of.OFPFC_DELETE)
            conn.send(msg)

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

    def _flood(self, connection: Connection, pkt_info: InPacketMeta):
        msg = of.ofp_packet_out()
        msg.in_port = pkt_info.iport
        msg.data = pkt_info.pkt.pack()
        # OFPP_FLOOD: output all openflow ports expect the input port and those with
        #    flooding disabled via the OFPPC_NO_FLOOD port config bit
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
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

    def _handle_fwd(self, dpid: int, connection: Connection, pkt_info: InPacketMeta):
        dport = self.l2routes[dpid].get_port(pkt_info.dmac)
        # if we have a route, add the rule and send it
        if dport is not None:
            log.debug("Trying to forward packet using rules")
            self._install_fwd_rule(connection, pkt_info, dport)
        # otherwise flood it to local nodes
        else:
            log.debug("Unknown swdport for dmac on DPID, flooding packet to all ports.")
            self._flood(connection, pkt_info)
        # if neither work, that means we didn't have a route and the packet dies

    def _handle_arp(self, dpid: int, connection: Connection, pkt_info: InPacketMeta):
        a: arp = pkt_info.pkt.next
        # arp is request, propagating is too hard at l2
        # have the switch pretend to be a router and respond to the arp
        if a.opcode == arp.REQUEST:
            # last octet is always the host number
            dmac = host_ip_to_mac(pkt_info.dst_ip)
            # construct and send reply
            r = arp(
                hwtype=a.hwtype,
                prototype=a.prototype,
                hwlen=a.hwlen,
                protolen=a.protolen,
                opcode=arp.REPLY,
                hwdst=a.hwsrc,
                protodst=a.protosrc,
                protosrc=a.protodst,
                hwsrc=dmac,
            )
            e = ethernet(type=ethernet.ARP_TYPE, src=dmac, dst=a.hwsrc)
            e.set_payload(r)
            log.debug(f"switch {dpid} sending ARP response on behalf of {a.protodst}, {dmac}")
            msg = of.ofp_packet_out()
            msg.data = e.pack()
            msg.actions.append(of.ofp_action_output(port=pkt_info.iport))
            connection.send(msg)
        # arp is something else (probably a reply), handle as a normal packet
        else:
            log.debug(f"Arp packet of type {a.opcode} found, forwarding.")
            self._handle_fwd(connection, pkt_info)

    def _handle_PacketIn(self, event: PacketIn):
        # ipv6 is stupid, ignore it
        if event.parsed.effective_ethertype == ethernet.IPV6_TYPE:
            return
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

        log.debug("Routing packet")
        log.debug(f"My l2table is: {self.l2routes[dpid].mac_table}")

        # learn mac mapping for directly connected nodes only
        if self.l2routes[dpid].get_port(pkt_info.smac) is None and pkt_info.smac != EthAddr(
            "ff:ff:ff:ff:ff:ff"
        ):
            self.l2routes[dpid].register_mac(pkt_info.smac, pkt_info.iport)

        # the controller can directly resolve arp requests using some invariants
        if pkt_type == InPacketType.ARP:
            self._handle_arp(dpid, event.connection, pkt_info)
        else:
            self._handle_fwd(dpid, event.connection, pkt_info)

    def _handle_LinkEvent(self, event: LinkEvent):
        # test that discovery works
        if self.debug:
            log.debug("======LINK EVT========")
        self.graph.update_from_linkevent(event)
        self.graph_updated = True
        if event.added:
            # discovered connections are EXTERNAL between switches and should not accept arp
            # flood
            self._set_port_flood_mode(event.link.dpid1, event.link.port1, False)
            self._set_port_flood_mode(event.link.dpid2, event.link.port2, False)
        if event.removed:
            # re-enable flooding, clear openflow rules on switches that would sinkhole
            self._set_port_flood_mode(event.link.dpid1, event.link.port1, True)
            self._set_port_flood_mode(event.link.dpid2, event.link.port2, True)
            self._clear_rules_for_port(event.link.dpid1, event.link.port1)
            self._clear_rules_for_port(event.link.dpid2, event.link.port2)
        self.hook_link_event(event)

    def _handle_ConnectionUp(self, event: ConnectionUp):
        if self.debug:
            log.debug("=========== SW UP EVT ===========")
        log.debug(f"switch {event.dpid} is coming up")
        self.graph.register_node(event.dpid)
        self.l2routes[event.dpid] = MacTable()
        self.hook_connection_up(event)
