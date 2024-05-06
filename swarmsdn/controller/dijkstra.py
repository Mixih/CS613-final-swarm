from heapq import heappush, heappop

import pox.openflow.discovery

from pox.core import core
from pox.openflow.discovery import LinkEvent
from pox.lib.addresses import EthAddr

from swarmsdn.graph import NetLinkUnidir, NetGraphNodeDir
from swarmsdn.controller.base import GraphControllerBase
from swarmsdn.openflow import InPacketMeta, InPacketType
from swarmsdn.util import PrioritizedItem, dpid_to_mac

log = core.getLogger()


class DijkstraController(GraphControllerBase):
    def __init__(self):
        super().__init__()

    def hook_handle_link_event(self, event: LinkEvent):
        pass

    def hook_packet_in_prerouting(self, pkt_info: InPacketMeta, packet_type: InPacketType) -> bool:
        # update tables if the topo changed
        if self.graph_updated:
            self.run_dijkstra_update()
            self.graph_updated = False
        return True

    def run_dijkstra_update(self):
        for _, node in self.graph.nodes.items():
            self.run_dijkstra_from_node(node)
        # flush openflow tables to force all tables to update
        self.clear_all_of_tables()

    def _unwind_backlinks(self, src: NetGraphNodeDir, table: dict[int, NetLinkUnidir]):
        out: dict[int, int] = {}
        dpids_remaining = set(table.keys())
        while True:
            if len(dpids_remaining) == 0:
                break
            dpid = dpids_remaining.pop()
            new_dpids = set([dpid])
            backref = table[dpid]
            port = None
            # iterate all the way back until we hit the source node
            while backref.dnode.dpid != src.dpid:
                # shortcut: if we know that our parent is routed through a port, we must
                # also be routed through that port
                if backref.dnode.dpid in out:
                    port = out[backref.dnode.dpid]
                    break
                # advance
                dpid = backref.dnode.dpid
                backref = table[dpid]
                new_dpids.add(dpid)
                dpids_remaining.remove(dpid)
            if port is None:
                port = backref.dport
            for dpid in new_dpids:
                out[dpid] = port
        log.debug(f"dpid/port table: {out}")
        return out

    def run_dijkstra_from_node(self, src: NetGraphNodeDir):
        pq = []
        prev: dict[int, NetLinkUnidir] = {}
        costs: dict[int, int] = {dpid: -1 for dpid in self.graph.nodes}

        log.debug("starting dijkstra")
        costs[src.dpid] = 0
        heappush(pq, PrioritizedItem(priority=0, item=src))
        while len(pq) != 0:
            pq_item = heappop(pq)
            cost = pq_item.priority
            u: NetGraphNodeDir = pq_item.item
            for next_dpid, link in u.links.items():
                v = link.dnode
                candidate_cost = cost + link.cost
                if costs[v.dpid] == -1 or candidate_cost < costs[v.dpid]:
                    costs[v.dpid] = candidate_cost
                    prev[v.dpid] = NetLinkUnidir(
                        cost=link.cost, sport=link.dport, dport=link.sport, dnode=u
                    )
                    heappush(pq, PrioritizedItem(priority=candidate_cost, item=v))
        self.l2routes[src.dpid].flush()
        print(len(prev))
        log.debug("starting unwind")
        for dpid, port in self._unwind_backlinks(src, prev).items():
            mac_for_dpid = dpid_to_mac(dpid)
            self.l2routes[src.dpid].register_mac(mac_for_dpid, port)


def launch():
    pox.openflow.discovery.launch(link_timeout=5)

    def start_controller():
        log.debug("Starting dijkstra controller...")
        core.registerNew(DijkstraController)

    core.call_when_ready(start_controller, "openflow_discovery")
