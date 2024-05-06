from dataclasses import dataclass, field

from pox.openflow.discovery import LinkEvent


@dataclass
class NetLink:
    cost: int
    port1: int
    port2: int
    node1: "NetGraphNode"
    node2: "NetGraphNode"
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"<{self.__class__.__name__}, cost: {self.cost}, port1: {self.port1}, "
        f"port2: {self.port2}, node1: {self.node1.dpid}, node2: {self.node2.dpid}>"

@dataclass
class NetLinkUnidir:
    cost: int
    sport: int
    dport: int
    dnode: "NetGraphNode"

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"<{self.__class__.__name__}, cost: {self.cost}, sport: {self.sport}, dport: {self.dport}, dnode:{self.dnode.dpid}>"

@dataclass
class NetGraphNode:
    dpid: int
    links: dict[int, NetLink] = field(default_factory=dict)

@dataclass
class NetGraphNodeDir:
    dpid: int
    links: dict[int, NetLinkUnidir] = field(default_factory=dict)


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


class NetGraphBidir(NetGraph):
    """
    Variant of the above graph with two bidirectional links per node to make certain
    algorithms more efficient to implement
    """

    def __init__(self):
        super().__init__()

    def add_connection(self, first_dpid: int, first_port: int, second_dpid: int, second_port: int):
        if first_dpid == second_dpid:
            return
        node1 = self.nodes[first_dpid]
        node2 = self.nodes[second_dpid]
        if node2.dpid not in node1.links:
            node1.links[node2.dpid] = NetLinkUnidir(
                cost=1, sport=first_port, dport=second_port, dnode=node2
            )
        if node1.dpid not in node2.links:
            node2.links[node1.dpid] = NetLinkUnidir(
                cost=1, sport=second_port, dport=first_port, dnode=node1
            )
