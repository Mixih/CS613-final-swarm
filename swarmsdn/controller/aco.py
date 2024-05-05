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

    def initialize_ants(self):
        # ants start at random nodes in the graph
        for _ in range(self.num_ants):
            start_node = self.graph.random_node()
            ant = Ant(start_node, self.graph, self.alpha, self.beta)
            self.ants.append(ant)

    def run_ants(self):
        # for each ant find a path through the network
        for ant in self.ants:
            while True:
                if not ant.move_to_next_node():
                    break
            ant.deposit_pheromones()
            ant.reset_ant()

        # kill pheromones on all edges
        self.graph.evaporate_pheromones(self.evaporation_rate)

    def hook_handle_connection_up(self, event: ConnectionUp):
        log.debug("New device connected with DPID: %s", event.dpid)
        # Handle new connections here TODO: not sure what the ideal number of ants should be but i think it makes sense to scale quadratically? you?

    def hook_handle_link_event(self, event: LinkEvent):
        log.debug("Link event: %s", "Added" if event.added else "Removed")
        self.graph.update_from_linkevent(event)
        # Optionally reset ant paths if the topology changes significantly TODO:

def launch():
    def start_aco_controller():
        log.info("Starting ACO controller...")
        core.registerNew(ACOController)

    core.call_when_ready(start_aco_controller, ['openflow_discovery'])


