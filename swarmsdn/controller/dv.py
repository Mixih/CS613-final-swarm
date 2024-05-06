import pox.openflow.discovery
from pox.core import core
from pox.lib.addresses import EthAddr
from pox.openflow.discovery import LinkEvent
from pox.openflow.of_01 import ConnectionUp
from swarmsdn.controller.base import GraphControllerBase
from swarmsdn.graph import NetGraphNodeDir
from swarmsdn.openflow import InPacketMeta, InPacketType
from swarmsdn.util import dpid_to_mac

log = core.getLogger()


class DistanceVectorController(GraphControllerBase):

    DV_ITER_LIMIT = 1000

    def __init__(self):
        super().__init__()
        self.dvs_for_switch: dict[int, dict[EthAddr, int]] = {}

    def hook_packet_in_prerouting(self, pkt_info: InPacketMeta, packet_type: InPacketType) -> bool:
        # update tables if the topo changed
        if self.graph_updated:
            self._run_dv_update()
            self.graph_updated = False
        return True

    def hook_connection_up(self, event: ConnectionUp):
        self.dvs_for_switch[event.dpid] = {}

    def hook_link_event(self, event: LinkEvent):
        if event.removed:
            # drop dv tables for switches that changed links
            self.dvs_for_switch[event.link.dpid1].clear()
            self.dvs_for_switch[event.link.dpid2].clear()

    def _run_dv_update(self):
        i = 0
        while i < self.DV_ITER_LIMIT:
            log.debug(f"Running DV update iteration {i}")
            updated = False
            for _, node in self.graph.nodes.items():
                updated |= self._update_dv_at_node(node)
            if updated is False:
                break
            i += 1
        # flush openflow tables to force all tables to update
        self.clear_all_of_tables()

    def _update_dv_at_node(self, node: NetGraphNodeDir):
        # seed dv with our mac at zero cost
        new_table = {}
        dv = {dpid_to_mac(node.dpid): 0}
        for neighbor_dpuid, neighbor_link in node.links.items():
            for mac, cost in self.dvs_for_switch[neighbor_dpuid].items():
                next_hop_cost = cost + neighbor_link.cost
                if mac not in dv or dv[mac] != 0 and next_hop_cost < dv[mac]:
                    dv[mac] = next_hop_cost
                    new_table[mac] = neighbor_link.sport
        if dv == self.dvs_for_switch[node.dpid]:
            return False
        # perform updates
        self.dvs_for_switch[node.dpid] = dv
        self.l2routes[node.dpid].flush()
        for dst, port in new_table.items():
            self.l2routes[node.dpid].register_mac(dst, port)
        return True


def launch():
    pox.openflow.discovery.launch(link_timeout=5)

    def start_controller():
        log.debug("Starting dijkstra controller...")
        core.registerNew(DistanceVectorController)

    core.call_when_ready(start_controller, "openflow_discovery")
