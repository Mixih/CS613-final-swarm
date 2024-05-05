from dataclasses import dataclass, field

from pox.openflow.discovery import LinkEvent


@dataclass
class NetLink:
    cost: int
    port1: int
    port2: int
    node1: "NetGraphNode"
    node2: "NetGraphNode"

@dataclass
class NetLinkAnt:
    cost: int
    port1: int
    port2: int
    node1: "NetGraphNodeAnt"
    node2: "NetGraphNodeAnt"
    pheromone_level: float = 0.01

@dataclass
class NetGraphNodeAnt:
    dpid: int
    links: dict[int, NetLinkAnt] = field(default_factory=dict)

@dataclass
class NetGraphNode:
    dpid: int
    links: dict[int, NetLink] = field(default_factory=dict)

class NetGraphAnt:
    def __init__(self):
        self.nodes: dict[int, NetGraphNodeAnt] = {}

    def register_node(self, dpid: int):
        if dpid not in self.nodes:
            self.nodes[dpid] = NetGraphNodeAnt(dpid=dpid)

    def add_connection(self, first_dpid: int, first_port: int, second_dpid: int, second_port: int):
        if first_dpid not in self.nodes:
            self.register_node(first_dpid)
        if second_dpid not in self.nodes:
            self.register_node(second_dpid)

        node1 = self.nodes[first_dpid]
        node2 = self.nodes[second_dpid]
        link = NetLinkAnt(cost=1, port1=first_port, port2=second_port, node1=node1, node2=node2)

        node1.links[second_dpid] = link
        node2.links[first_dpid] = link
    
    def delete_connection(self, first_dpid: int, second_dpid: int):
        if first_dpid in self.nodes and second_dpid in self.nodes[first_dpid].links:
            del self.nodes[first_dpid].links[second_dpid]
        if second_dpid in self.nodes and first_dpid in self.nodes[second_dpid].links:
            del self.nodes[second_dpid].links[first_dpid]

    def update_from_linkevent(self, event: LinkEvent):
        if event.added:
            self.add_connection(event.link.dpid1, event.link.port1, event.link.dpid2, event.link.port2)
        elif event.removed:
            self.delete_connection(event.link.dpid1, event.link.dpid2)

    def random_node(self):
        return random.choice(list(self.nodes.keys()))

    def get_neighbors(self, node_id):
        return [node for node in self.nodes[node_id].links.keys()]

    def get_pheromone_level(self, from_node, to_node):
        return self.nodes[from_node].links[to_node].pheromone_level

    def update_pheromone_level(self, from_node, to_node, amount):
        self.nodes[from_node].links[to_node].pheromone_level += amount
        self.nodes[to_node].links[from_node].pheromone_level += amount  # Assuming undirected graph

    def evaporate_pheromones(self, evaporation_rate):
        for node in self.nodes.values():
            for link in node.links.values():
                link.pheromone_level *= (1 - evaporation_rate)

    def get_edge_cost(self, from_node, to_node):
        return self.nodes[from_node].links[to_node].cost


class NetGraph:
    def __init__(self):
        self.nodes: dict[int, NetGraphNode] = {}

    def register_node(self, dpid: int):
        assert dpid not in self.nodes
        self.nodes[dpid] = NetGraphNode(dpid=dpid)

    def add_connection(self, first_dpid: int, first_port: int, second_dpid: int, second_port: int):
        node1 = self.nodes[first_dpid]
        node2 = self.nodes[second_dpid]
        link = NetLink(cost=1, port1=first_port, port2=second_port, node1=node1, node2=node2)
        if node2.dpid not in node1.links:
            node1.links[node2.dpid] = link
        if node1.dpid not in node2.links:
            node2.links[node1.dpid] = link

    def delete_connection(self, first_dpid: int, second_dpid: int):
        node1 = self.nodes[first_dpid]
        node2 = self.nodes[second_dpid]
        if node2.dpid not in node1.links:
            del node1.adjacent[node2.dpid]
        if node1.dpid not in node2.links:
            del node2.adjacent[node1.dpid]

    def update_from_linkevent(self, event: LinkEvent):
        if event.added:
            self.add_connection(
                event.link.dpid1, event.link.port1, event.link.dpid2, event.link.port2
            )
        elif event.removed:
            self.delete_connection(event.link.dpid1, event.link.dpid2)
