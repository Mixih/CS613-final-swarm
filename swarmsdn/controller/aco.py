from pox.core import core
from pox.lib.revent import EventMixin
from pox.openflow.of_01 import ConnectionUp
from pox.openflow.discovery import LinkEvent
from swarmsdn.graph import NetGraphAnt
from swarmsdn.aco.ant import Ant
from swarmsdn.controller.base import GraphControllerBase

log = core.getLogger()

class ACOController(GraphControllerBase):
    def __init__(self, num_ants=10, alpha=1.0, beta=1.0, evaporation_rate=0.5, convergence_threshold = 0.05, max_iter = 100):
        super().__init__()
        self.num_ants = num_ants
        self.alpha = alpha
        self.beta = beta
        self.evaporation_rate = evaporation_rate
        self.ants = []
        self.initialize_ants()
        self.max_iter
        self.convergence_threshold = convergence_threshold

    def initialize_ants(self):
        # Initialize ants at random nodes in the graph
        for _ in range(self.num_ants):
            start_node = self.graph.random_node()
            ant = Ant(start_node, self.graph, self.alpha, self.beta)
            self.ants.append(ant)

    def run_ants(self):
        if self.iteration_count >= self.max_iterations:
            log.info("Maximum iters reached. Stopping ACO.")
            return
        self.iteration_count += 1
        # Each ant finds a path through the network and deposits pheromones
        for ant in self.ants:
            while ant.move_to_next_node():
                pass
            ant.deposit_pheromones()
            self.aggregate_path_data(ant)
            ant.reset_ant()
       converged = True
       for node in self.graph.nodes.values():
            for link in node.links.values():
                key = (link.node1.dpid, link.node2.dpid)
                current_level = link.pheromone_level
                if key in self.last_pheromone_levels:
                    if abs(current_level - self.last_pheromone_levels[key]) > self.convergence_threshold:
                        converged = False
                self.last_pheromone_levels[key] = current_level

        if converged:
            log.info("ACO converged after {} iterations.".format(self.iteration_count))
            self.output_forwarding_tables()
        else:
            log.info("ACO not yet converged, continuing to iteration # {}.".format(self.iteration_count))
            self.graph.evaporate_pheromones(self.evaporation_rate)

    def aggregate_path_data(self, ant):
        for i in range(len(ant.path) - 1):
            src_node, src_port = ant.path[i]
            dst_node, _ = ant.path[i + 1]
            if (src_node, dst_node) not in self.path_aggregation:
                self.path_aggregation[(src_node, dst_node)] = {'count': 0, 'port': src_port}
            self.path_aggregation[(src_node, dst_node)]['count'] += 1

    def output_forwarding_tables(self):
        forwarding_tables = {}
        for (src_node, dst_node), data in self.path_aggregation.items():
            if src_node not in forwarding_tables:
                forwarding_tables[src_node] = {}
            if data['count'] > forwarding_tables[src_node].get(dst_node, {}).get('count', 0):
                # Update if this path is more frequently used than the current stored one
                forwarding_tables[src_node][dst_node] = {'port': data['port'], 'count': data['count']}
        ## TODO: install forwarding tables here

        # flush openflow tables to force all tables to update
        self.clear_all_of_tables() 

    def adjust_ant_population(self):
        # Adjust abased on the number of network nodes
        current_nodes = len(self.graph.nodes)
        desired_ants = max(10, current_nodes **2 ) # scale quadratically
        if desired_ants != self.num_ants:
            self.num_ants = desired_ants
            self.initialize_ants()  # reinitialize ants
            log.info(f"Adjusted number of ants to {self.num_ants} due to network change.")

    def hook_handle_connection_up(self, event: ConnectionUp):
        log.debug("New device connected with DPID: %s", event.dpid)
        self.adjust_ant_population()
        self.run_ants()

    def hook_handle_link_event(self, event: LinkEvent):
        log.debug("Link event: %s", "Added" if event.added else "Removed")
        self.graph.update_from_linkevent(event)
        self.run_ants()

def launch():
    def start_aco_controller():
       log.info("Starting ACO controller...")
        core.registerNew(ACOController)

    core.call_when_ready(start_aco_controller, ['openflow_discovery'])

