from typing import cast

from pox.core import core
import pox.openflow.discovery
from pox.openflow.discovery import LinkEvent
from pox.openflow.of_01 import ConnectionUp

from swarmsdn.aco.ant import Ant
from swarmsdn.controller.base import GraphControllerBase
from swarmsdn.aco.graph import NetGraphAnt
from swarmsdn.util import dpid_to_mac
from swarmsdn.openflow import InPacketMeta, InPacketType

log = core.getLogger()


class ACOController(GraphControllerBase):
    def __init__(
        self,
        num_ants=10,
        alpha=1.0,
        beta=2.0,
        evaporation_rate=0.5,
        convergence_threshold=0.1,
        max_iterations=5,
    ):
        super().__init__(graph_class=NetGraphAnt)
        self.num_ants = num_ants
        self.alpha = alpha
        self.beta = beta
        self.evaporation_rate = evaporation_rate  # evaporation rate for the AOC
        self.convergence_threshold = convergence_threshold  # hyperparameter convergence threshold
        self.max_iterations = max_iterations  # limit for convergence loop
        self.last_pheromone_levels = {}  # tracking for aggregation
        # self.path_aggregation = {}  # aggregation to test for convergence
        self.ants = []  # to keep track of ants
        self.converged = False
        self.graph = cast(NetGraphAnt, self.graph)
        self.shortest_path_cost: dict[tuple[int, int], int] = {}

    def initialize_ants(self):
        for _ in range(self.num_ants):
            ant = Ant(self.graph, self.alpha, self.beta)
            self.ants.append(ant)

    def run_ants(self):
        iteration_count = 0
        converged = True
        self.shortest_path_cost.clear()


        while iteration_count < self.max_iterations:
            # clear all current routes
            for table in self.l2routes.values():
                table.flush()
            iteration_count += 1

            log.debug("iterating over ants")
            for ant in self.ants:
                # while ant.move_to_next_node():
                #     pass
                # ant.deposit_pheromones()
                # self.aggregate_path_data(ant)
                # ant.reset_ant()
                path = ant.run()
                self.aggregate_path_data(path)

            converged = True
            for node in self.graph.nodes.values():
                my_dpid = node.dpid
                for link in node.links.values():
                    current_level = link.pheromone_level
                    if my_dpid in self.last_pheromone_levels:
                        if (
                            abs(current_level - self.last_pheromone_levels[my_dpid])
                            > self.convergence_threshold
                        ):
                            converged = False
                    self.last_pheromone_levels[my_dpid] = current_level
            if converged:
                log.info("ACO converged after {} iterations.".format(iteration_count))
                break
            else:
                log.info(
                    "ACO not yet converged, continuing to iteration #{}.".format(iteration_count)
                )
                self.graph.evaporate_pheromones(self.evaporation_rate)
        if iteration_count >= self.max_iterations:
            log.info("Maximum iterations reached. Stopping ACO.")
        self.last_pheromone_levels = {}
        return converged

    # def aggregate_path_data(self, ant):
    #     for i in range(len(ant.path) - 1):
    #         src_node, src_port = ant.path[i]
    #         dst_node, _ = ant.path[i + 1]
    #         if (src_node, dst_node) not in self.path_aggregation:
    #             self.path_aggregation[(src_node, dst_node)] = {'count': 0, 'port': src_port}
    #         self.path_aggregation[(src_node, dst_node)]['count'] += 1

    def aggregate_path_data(self, path):
        if (len(path) < 2):
            return
        # print(ant.path)
        src_dpid, _ = path[0]
        src_port = path[1][1].sport
        assert src_dpid == path[1][1].snode.dpid
        running_cost = 0
        for i in range(0, len(path) - 1):
            this_dpid, _ = path[i]
            next_dpid, link = path[i + 1]
            running_cost += link.cost
            this_mac = dpid_to_mac(this_dpid)
            next_mac = dpid_to_mac(next_dpid)
            self.l2routes[src_dpid].try_remove(next)
            self.l2routes[src_dpid].register_mac(next_mac, src_port)
            self.l2routes[this_dpid].try_remove(next_mac)
            self.l2routes[this_dpid].register_mac(next_mac, link.sport)
            self.l2routes[next_dpid].try_remove(this_mac)
            self.l2routes[next_dpid].register_mac(this_mac, link.dport)

    # def output_forwarding_tables(self):
    #     for table in self.l2routes.values():
    #         table.flush()
    #     print(self.path_aggregation.items())
    #     for (src_node, dst_node), data in self.path_aggregation.items():
    #         dst_mac = dpid_to_mac(dst_node)
    #         port = data["port"]
    #         self.l2routes[src_node].register_mac(dst_mac, port)
    #     log.debug("Updated l2routes based on ACO findings.")

    def adjust_ant_population(self):
        current_nodes = len(self.graph.nodes)
        desired_ants = max(10, current_nodes**2)
        if desired_ants != self.num_ants:
            self.num_ants = desired_ants
            self.initialize_ants()
            log.info(f"Adjusted number of ants to {self.num_ants} due to network change.")

    def hook_connection_up(self, event: ConnectionUp):
        log.debug("New device connected with DPID: %s", event.dpid)
        self.adjust_ant_population()
        # self.run_ants()

    # def hook_link_event(self, event: LinkEvent):
    #     log.debug("Link event: %s", "Added" if event.added else "Removed")
    #     self.graph.update_from_linkevent(event)
    #     while self.converged == False:
    #         self.run_ants()

    def hook_packet_in_prerouting(self, pkt_info: InPacketMeta, packet_type: InPacketType):
        if self.graph_updated:
            self.run_ants()
            self.graph_updated = False
        return True


def launch():
    def start_aco_controller():
        log.info("Starting ACO controller...")
        core.registerNew(ACOController)

    pox.openflow.discovery.launch(link_timeout=5)
    core.call_when_ready(start_aco_controller, "openflow_discovery")
