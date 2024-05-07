import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.revent import EventMixin
from pox.openflow.of_01 import PacketIn, ConnectionUp, PortStatus
import random

class Ant:
    def __init__(self, start_node, graph, alpha=1.0, beta=1.0):
        self.graph = graph
        self.alpha = alpha
        self.beta = beta
        self.random_state = random.Random()
        self.reset_ant(start_node)

    def reset_ant(self, start_node=None):
        if start_node is None:
            start_node = self.graph.random_node()
        self.current_node = start_node
        self.path = [(start_node, None)]  # Initialize path with the start node and no port
        self.distance_traveled = 0.0
        self.pheromone_deposit = 0.0

    def select_next_node(self):
        neighbors = self.graph.get_neighbors(self.current_node)
        probabilities = []
        next_ports = []

        if not neighbors:
            return None, None

        for neighbor in neighbors:
            link = self.graph.nodes[self.current_node].links[neighbor]
            pheromone_level = link.pheromone_level
            heuristic_value = 1.0 / link.cost if link.cost > 0 else float('inf')
            probability = (pheromone_level ** self.alpha) * (heuristic_value ** self.beta)
            probabilities.append(probability)
            next_ports.append(link.port1)  # assuming port1 is correct TODO: /validate this assumption.

        total = sum(probabilities)
        if total == 0:
            random_index = random.randint(0, len(neighbors) - 1)
            return neighbors[random_index], next_ports[random_index]

        probabilities = [p / total for p in probabilities]
        chosen_index = random.choices(range(len(neighbors)), weights=probabilities, k=1)[0]
        return neighbors[chosen_index], next_ports[chosen_index]

    def move_to_next_node(self):
        next_node, next_port = self.select_next_node()
        if next_node is None:
            return False  # no valid moves

        self.path.append((next_node, next_port))  # append the next node and port
        self.distance_traveled += self.graph.get_edge_cost(self.current_node, next_node)
        self.current_node = next_node
        return True  # successful

    def deposit_pheromones(self):
        if self.distance_traveled > 0:  # check if the ant has moved
            for i in range(len(self.path) - 1):
                from_node, _ = self.path[i]
                to_node, _ = self.path[i + 1]
                pheromone_to_deposit = 1.0 / self.distance_traveled
                self.graph.update_pheromone_level(from_node, to_node, pheromone_to_deposit)

