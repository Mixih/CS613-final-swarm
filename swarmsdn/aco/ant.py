import random

from swarmsdn.aco.graph import NetGraphAnt, NetGraphNodeAnt, NetLinkAnt


class Ant:
    def __init__(self, graph, alpha=1.0, beta=1.0):
        self.graph: NetGraphAnt = graph
        self.alpha = alpha
        self.beta = beta
        self.random_state = random.Random()
        # self.pheromone_deposit: float = 0.0
        # self.distance_traveled: float = 0.0
        # self.path: list[tuple[int, NetLinkAnt]] = []
        # self.current_node: int = -1
        # self.visited: set[int] = set()

        # self.reset_ant()

    def reset_ant(self):
        pass
    #     start_node = self.graph.random_node()
    #     # self.current_node = start_node
    #     self.path = [(start_node, None)]  # Initialize path with the start node and no port
    #     self.distance_traveled = 0.0
    #     self.pheromone_deposit = 0.0
    #     self.visited.clear()
    #     self.visited.add(start_node)

    def select_next_node(self, current_node, visited):
        neighbors = self.graph.get_neighbors(current_node)
        probabilities = []
        src_links = []

        if not neighbors:
            return None, None

        for neighbor in neighbors:
            probability = 0
            link = self.graph.nodes[current_node].links[neighbor]
            if neighbor not in visited:
                assert link.cost > 0
                pheromone_level = link.pheromone_level
                heuristic_value = 1.0 / link.cost
                probability = (pheromone_level**self.alpha) * (heuristic_value**self.beta)
            probabilities.append(probability)
            src_links.append(link)

        total = sum(probabilities)
        if total == 0:
            random_index = random.randint(0, len(neighbors) - 1)
            return neighbors[random_index], src_links[random_index]

        probabilities = [p / total for p in probabilities]
        chosen_index: int = random.choices(range(len(neighbors)), weights=probabilities, k=1)[0]
        return neighbors[chosen_index], src_links[chosen_index]

    def move_to_next_node(self) -> tuple[bool, bool]:
        next_node, src_link = self.select_next_node()
        if next_node is None or next_node in self.visited:
            return False  # no valid moves

        self.visited.add(self.current_node)
        assert self.current_node == src_link.snode.dpid
        assert next_node == src_link.dnode.dpid
        self.path.append((next_node, src_link))  # append the next node and port
        self.distance_traveled += self.graph.get_edge_cost(self.current_node, next_node)
        self.current_node = next_node
        return True  # successful

    def run(self):
        start_node = self.graph.random_node()
        current_node = start_node
        path: list[tuple[int, NetLinkAnt]] = [(start_node, None)]
        visited = set([start_node])
        distance_traveled = 0.0
        while True:
            next_node, src_link = self.select_next_node(current_node, visited)
            if next_node is None or next_node in visited:
                break  # no valid moves

            visited.add(current_node)
            assert current_node == src_link.snode.dpid
            assert next_node == src_link.dnode.dpid
            path.append((next_node, src_link))  # append the next node and port
            distance_traveled += self.graph.get_edge_cost(current_node, next_node)
            current_node = next_node
        self.deposit_pheromones(path, distance_traveled)
        return path

    def deposit_pheromones(self, path, distance_traveled):
        if distance_traveled > 0:  # check if the ant has moved
            for i in range(len(path) - 1):
                from_node, _ = path[i]
                to_node, _ = path[i + 1]
                pheromone_to_deposit = 1.0 / distance_traveled
                self.graph.update_pheromone_level(from_node, to_node, pheromone_to_deposit)
