import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery

from pox.core import core
from pox.lib.revent import EventMixin
from pox.openflow.of_01 import PacketIn, ConnectionUp, PortStatus
from pox.openflow.discovery import LinkEvent

from swarmsdn.graph import NetGraph
from swarmsdn.controller.base import GraphControllerBase

log = core.getLogger()


class DijkstraController(GraphControllerBase):
    def __init__(self):
        super().__init__()

    def hook_handle_link_event(self, event: LinkEvent):
        pass


def launch():
    pox.openflow.discovery.launch()

    def start_controller():
        log.debug("Starting dijkstra controller...")
        core.registerNew(DijkstraController)

    core.call_when_ready(start_controller, "openflow_discovery")
