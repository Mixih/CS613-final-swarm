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
        # this is for initializaiton or reseting conditions
        if start_node is None:
            start_node = self.graph.random_node()
        self.current_node = start_node
        self.path = [start_node]
        self.distance_traveled = 0.0
        self.pheromone_deposit = 0.0

    def select_next_node(self):
        neighbors = self.graph.get_neighbors(self.current_node)
        probabilities = []

        if not neighbors:
            return None  # N neighbors to move to, handle this case in move_to_next_node

        for neighbor in neighbors:
            pheromone_level = self.graph.get_pheromone_level(self.current_node, neighbor)
            heuristic_value = 1.0 / self.graph.get_edge_cost(self.current_node, neighbor)
            probability = (pheromone_level ** self.alpha) * (heuristic_value ** self.beta)
            probabilities.append(probability)

        total = sum(probabilities)
        if total == 0:
            return random.choice(neighbors)  # prevent division by zero if total pirobability is 0

        probabilities = [p / total for p in probabilities]
        chosen_node = self.random_state.choices(neighbors, weights=probabilities, k=1)[0]
        return chosen_node

    def move_to_next_node(self):
        next_node = self.select_next_node()
        if next_node is None:
            return False  # No valid moves

        self.path.append(next_node)
        self.distance_traveled += self.graph.get_edge_cost(self.current_node, next_node)
        self.current_node = next_node
        return True  # if the ant moved then retuern true

    def deposit_pheromones(self):
        if self.distance_traveled > 0:  # ant can only move in a positive direction
            for i in range(len(self.path) - 1):
                from_node = self.path[i]
                to_node = self.path[i + 1]
                pheromone_to_deposit = 1.0 / self.distance_traveled
                self.graph.update_pheromone_level(from_node, to_node, pheromone_to_deposit)

