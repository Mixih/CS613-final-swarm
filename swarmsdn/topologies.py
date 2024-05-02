from mininet.topo import Topo


class RoutableNodeTopo(Topo):
    def __init__(self, hosts: int):
        self.host_cnt = hosts
        self.mandatory_links: set[tuple[str, str]] = set()
        super().__init__()

    def build(self):
        # build modeled Ad-hoc nodes as a 1:1 host switch combo
        for i in range(0, self.host_cnt):
            sconfig = {"dpid": f"{i: 016x}"}
            self.addSwitch(f"s{i}", **sconfig)
            self.addHost(f"h{i}", ip=f"10.0.{i}.1")
            self.addLink(f"h{i}", f"s{i}")
        # build the backbone link to ensure that all nodes are routable
        for i in range(0, self.host_cnt - 1):
            link = (f"s{i}", f"s{i+1}")
            self.addLink(*link)
            self.mandatory_links.add(link)
