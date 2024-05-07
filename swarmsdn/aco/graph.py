import random
from dataclasses import dataclass, field

from pox.openflow.discovery import LinkEvent

from swarmsdn.graph import INetGraph


@dataclass
class NetLinkAnt:
    cost: int
    sport: int
    dport: int
    snode: "NetGraphNodeAnt"
    dnode: "NetGraphNodeAnt"
    pheromone_level: float = 0.01

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return (f"<{self.__class__.__name__}, cost: {self.cost}, sport: {self.sport},"
                f"dport: {self.dport}, snode: {self.snode.dpid}, dnode: {self.dnode.dpid},"
                f"pheremone_level: {self.pheromone_level}>")


@dataclass
class NetGraphNodeAnt:
    dpid: int
    links: dict[int, NetLinkAnt] = field(default_factory=dict)


class NetGraphAnt(INetGraph):
    def __init__(self):
        self.nodes: dict[int, NetGraphNodeAnt] = {}

    def register_node(self, dpid: int):
        if dpid not in self.nodes:
            self.nodes[dpid] = NetGraphNodeAnt(dpid=dpid, active_ports=set([1]))

    def add_connection(self, first_dpid: int, first_port: int, second_dpid: int, second_port: int):
        node1 = self.nodes[first_dpid]
        node2 = self.nodes[second_dpid]
        node1.active_ports.add(first_port)
        node2.active_ports.add(first_port)
        if node2.dpid not in node1.links:
            node1.links[node2.dpid] = NetLinkAnt(
                cost=1, sport=first_port, dport=second_port, snode=node1, dnode=node2
            )
        if node1.dpid not in node2.links:
            node2.links[node1.dpid] = NetLinkAnt(
                cost=1, sport=second_port, dport=first_port, snode=node2, dnode=node1
            )

    def delete_connection(self, first_dpid: int, second_dpid: int):
        node1 = self.nodes[first_dpid]
        node2 = self.nodes[second_dpid]
        if node2.dpid in node1.links:
            del node1.links[node2.dpid]
        if node1.dpid in node2.links:
            del node2.links[node1.dpid]

    def update_from_linkevent(self, event: LinkEvent):
        if event.added:
            self.add_connection(
                event.link.dpid1, event.link.port1, event.link.dpid2, event.link.port2
            )
        elif event.removed:
            self.delete_connection(event.link.dpid1, event.link.dpid2)

    def random_node(self) -> int:
        return random.choice(list(self.nodes.keys()))

    def get_neighbors(self, node_id) -> list[int]:
        return list(self.nodes[node_id].links.keys())

    def get_pheromone_level(self, from_node, to_node) -> float:
        return self.nodes[from_node].links[to_node].pheromone_level

    def update_pheromone_level(self, from_node, to_node, amount) -> None:
        self.nodes[from_node].links[to_node].pheromone_level += amount
        self.nodes[to_node].links[from_node].pheromone_level += amount  # Assuming undirected graph

    def evaporate_pheromones(self, evaporation_rate):
        for node in self.nodes.values():
            for link in node.links.values():
                link.pheromone_level *= 1 - evaporation_rate

    def clear_pheromones(self, evaporation_rate):
        for node in self.nodes.values():
            for link in node.links.values():
                link.pheromone_level = 0.0

    def get_edge_cost(self, from_node, to_node) -> int:
        return self.nodes[from_node].links[to_node].cost
