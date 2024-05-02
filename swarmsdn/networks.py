from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel, info
from random import randint, sample
import random

from swarmsdn.topologies import RoutableNodeTopo


class AdHocNetwork:
    def __init__(
        self,
        time_steps: int,
        seed: int,
        host_cnt: int,
        starting_links: int,
        dynamic_links: int,
        controller_ip: str,
    ):
        self.time_steps = time_steps
        self.starting_links = starting_links
        self.dynamic_links = dynamic_links
        self.current_links: set[tuple[str, str]] = set()

        self.started = False
        self.topo = RoutableNodeTopo(host_cnt)
        self.net = Mininet(
            topo=self.topo, controller=lambda name: RemoteController(name, ip=controller_ip)
        )
        random.seed(seed)
        setLogLevel("info")

    def run_assessment_for_step(self):
        info("    TODO: performance assessments\n")

    def wait_for_updates(self):
        info("    TODO: IMPLEMENT WAIT.\n")

    def drop_random_links(self):
        drop_target = self.dynamic_links
        while drop_target != 0:
            current_links_as_list = list(self.current_links)
            links_to_drop = sample(current_links_as_list, k=drop_target)
            info(
                "Dropping links: "
                + str([(link.intf1.node.name, link.intf2.node.name) for link in links_to_drop])
            )
            for link in links_to_drop:
                self.net.delLink(link)
                self.current_links.remove(link)
                drop_target -= 1

    def add_random_links(self, cnt: int):
        added_links = 0
        while added_links != cnt:
            fst_idx = randint(0, self.topo.host_cnt - 1)
            snd_idx = randint(0, self.topo.host_cnt - 1)
            fst_node = self.net.switches[fst_idx]
            snd_node = self.net.switches[snd_idx]
            if fst_idx == snd_idx or self.net.linksBetween(fst_node, snd_node) != []:
                continue
            link = self.net.addLink(fst_node, snd_node)
            self.current_links.add(link)
            added_links += 1

    def update_links(self):
        self.drop_random_links()
        self.add_random_links(self.dynamic_links)

    def stop_net(self):
        if self.started:
            self.net.stop()

    def run(self):
        self.net.start()
        self.started = True

        self.add_random_links(self.starting_links)
        self.add_random_links(self.dynamic_links)

        for t in range(0, self.time_steps):
            info(f"Timestep t={t}\n")
            info("Updating links...\n")
            self.update_links()
            info("Waiting for table updates...\n")
            self.wait_for_updates()
            info("Running assessment...\n")
            self.run_assessment_for_step()

        self.stop_net()
        self.started = False
