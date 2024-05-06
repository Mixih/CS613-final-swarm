from random import sample
from csv import DictWriter
import random
from time import sleep

from mininet.cli import CLI
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import RemoteController
from mininet.log import setLogLevel, info

from swarmsdn.topology import RoutableNodeTopo


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
        self.cur_time_step = 0
        self.starting_links = starting_links
        self.dynamic_links = dynamic_links
        self.current_links: set[tuple[str, str]] = set()

        self.started = False
        self.topo = RoutableNodeTopo(host_cnt)
        self.active_pool = self.topo.optional_links
        self.inactive_pool = set()
        self.net = Mininet(
            topo=self.topo,
            controller=lambda name: RemoteController(name, ip=controller_ip),
            listenPort=6633,
            waitConnected=True,
            link=TCLink,
        )
        random.seed(seed)
        setLogLevel("info")

        # logging
        self.datafile = open(
            f"data/ping_adhoc_s{seed}_ts{time_steps}_h{host_cnt}_sl{starting_links}_dl{dynamic_links}.csv",
            "w",
            newline="",
        )
        self.data_writer = DictWriter(
            self.datafile,
            fieldnames=[
                "timestep",
                "batch",
                "src",
                "dst",
                "sent",
                "recieved",
                "rtt",
            ],
        )
        self.data_writer.writeheader()

    def run_assessment_for_step(self):
        # CLI(self.net)
        for batch in range(0, 2):
            pingouts = self.net.pingAllFull()
            for pingout in pingouts:
                src, dst, stats = pingout
                row = {
                    "timestep": self.cur_time_step,
                    "batch": batch,
                    "src": src.name,
                    "dst": dst.name,
                    "sent": stats[0],
                    "recieved": stats[1],
                    # this is technically RTTMIN, but since the pingall command only issues the
                    # ping once, it's simply the rtt
                    "rtt": stats[2],
                }
                self.data_writer.writerow(row)

    def wait_for_updates(self):
        sleep(10)

    def _link_to_node_names(self, link: tuple[int, int]):
        return (f"s{link[0]}", f"s{link[1]}")

    def drop_all_links(self):
        for link in self.active_pool:
            self.net.configLinkStatus(*self._link_to_node_names(link), "down")
            self.inactive_pool.add(link)
        self.active_pool.clear()

    def drop_random_links(self):
        current_links_as_list = list(self.active_pool)
        links_to_drop = sample(current_links_as_list, k=self.dynamic_links)
        info(f"Dropping links: {links_to_drop}\n")
        for link in links_to_drop:
            self.net.configLinkStatus(*self._link_to_node_names(link), "down")
            self.inactive_pool.add(link)
        for link in links_to_drop:
            self.active_pool.remove(link)

    def add_random_links(self, cnt: int):
        assert len(self.inactive_pool) >= cnt
        current_links_as_list = list(self.inactive_pool)
        links_to_add = sample(current_links_as_list, k=self.dynamic_links)
        info(f"Adding links: {links_to_add}\n")
        for link in links_to_add:
            self.net.configLinkStatus(*self._link_to_node_names(link), "up")
            self.active_pool.add(link)
        for link in links_to_add:
            self.inactive_pool.remove(link)

    def update_links(self):
        self.drop_random_links()
        self.add_random_links(self.dynamic_links)

    def stop_net(self):
        self.datafile.close()
        if self.started:
            self.net.stop()

    def disable_ipv6(self):
        """
        IPV6 messages clutter the logs, just disable them to prevent the clutter
        Ref: https://gist.github.com/tudang/87da66215116e2ba5afd250a9fb8a9c8
        """
        for h in self.net.hosts:
            print(f"{h}: disable ipv6")
            h.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
            h.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
            h.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

    def run(self):
        self.net.start()
        self.disable_ipv6()
        self.started = True

        self.drop_all_links()
        self.add_random_links(self.starting_links)
        self.add_random_links(self.dynamic_links)
        # self.wait_for_updates()

        for t in range(0, self.time_steps):
            self.cur_time_step = t
            info("=============\n")
            info(f"Timestep t={t}\n")
            info("Updating links...\n")
            self.update_links()
            info("Waiting for table updates...\n")
            self.wait_for_updates()
            info("Running assessment...\n")
            self.run_assessment_for_step()

        self.stop_net()
        self.started = False
