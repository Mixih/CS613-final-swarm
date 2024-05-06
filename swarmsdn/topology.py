from mininet.topo import Topo


class RoutableNodeTopo(Topo):
    def __init__(self, hosts: int):
        assert hosts < 256
        self.host_cnt = hosts
        self.backbone_links: set[tuple[int, int]] = set()
        self.optional_links: set[tuple[int, int]] = set()
        super().__init__()

    def _add_link(self, pool: set[tuple[int, int]], link: tuple[int, int]):
        self.addLink(*[f"s{ln}" for ln in link])
        pool.add(link)

    def build(self):
        # build modeled Ad-hoc nodes as a 1:1 host switch combo
        for i in range(0, self.host_cnt):
            sconfig = {"dpid": f"{i:016x}"}
            self.addSwitch(f"s{i}", **sconfig)
            self.addHost(f"h{i}", ip=f"10.0.0.{i}", mac=f"02:00:00:00:ff:{i:02x}")
            self.addLink(f"h{i}", f"s{i}")
        # build fully connected components
        for i in range(0, self.host_cnt - 1):
            for j in range(i, self.host_cnt - 1):
                if i == j:
                    continue
                if j - 1 == i:
                    # build the backbone link to ensure that all nodes are routable
                    self._add_link(self.backbone_links, (i, j))
                else:
                    self._add_link(self.optional_links, (i, j))
