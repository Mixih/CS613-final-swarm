from pox.core import core
from pox.lib.revent import EventMixin
from pox.openflow.of_01 import ConnectionUp
from pox.openflow.discovery import LinkEvent
from swarmsdn.graph import NetGraphAnt
from swarmsdn.aco.ant import Ant
from swarmsdn.controller.base import GraphControllerBase

log = core.getLogger()

class ACOController(GraphControllerBase):
    def __init__(self, num_ants=10, alpha=1.0, beta=1.0, evaporation_rate=0.5):
        super().__init__()
        self.num_ants = num_ants
        self.alpha = alpha
        self.beta = beta
        self.evaporation_rate = evaporation_rate
        self.ants = []
        self.initialize_ants()
        self.global_counter = 0  # Tracks number of topology change events
        self.last_reset = 1  # Tracks the last event index at which ants were reset

    def initialize_ants(self):
        # Initialize ants at random nodes in the graph
        for _ in range(self.num_ants):
            start_node = self.graph.random_node()
            ant = Ant(start_node, self.graph, self.alpha, self.beta)
            self.ants.append(ant)

    def run_ants(self):
        # Each ant finds a path through the network and deposits pheromones
        for ant in self.ants:
            while ant.move_to_next_node():
                pass
            ant.deposit_pheromones()
            ant.reset_ant()
        self.graph.evaporate_pheromones(self.evaporation_rate)

    def adjust_ant_population(self):
        # Adjust the number of ants based on the number of network nodes
        current_nodes = len(self.graph.nodes)
        desired_ants = max(10, current_nodes **2 ) # scale quadratically
        if desired_ants != self.num_ants:
            self.num_ants = desired_ants
            self.initialize_ants()  # Reinitialize ants
            log.info(f"Adjusted number of ants to {self.num_ants} due to network change.")

    def hook_handle_connection_up(self, event: ConnectionUp):
        log.debug("New device connected with DPID: %s", event.dpid)
        self.adjust_ant_population()
        self.global_counter += 1

    def hook_handle_link_event(self, event: LinkEvent):
        log.debug("Link event: %s", "Added" if event.added else "Removed")
        self.graph.update_from_linkevent(event)
        self.global_counter += 1
        # Reset ants if significant topology changes have occurred
        if self.global_counter / ((self.last_reset + 1) * 4) > 0.75:
            for ant in self.ants:
                ant.reset_ant()
            self.last_reset = self.global_counter

def launch():
    def start_aco_controller():
        log.info("Starting ACO controller...")
        core.registerNew(ACOController)

    core.call_when_ready(start_aco_controller, ['openflow_discovery'])

