import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery

from pox.core import core
from pox.lib.revent import EventMixin
from pox.openflow.of_01 import PacketIn, ConnectionUp, PortStatus
from pox.openflow.discovery import LinkEvent

log = core.getLogger()


class DijkstraController(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        self.listenTo(core.openflow_discovery)
        core.openflow_discovery.addListeners(self)

    def _handle_LinkEvent(self, event: LinkEvent):
        # test that discovery works
        log.debug(event)

    def _handle_openflow_PortStatus(self, event: PortStatus):
        log.debug(event)

    def _handle_ConnectionUp(self, event: ConnectionUp):
        log.debug("=========== SW UP EVT ===========")


def launch():
    pox.openflow.discovery.launch()

    def start_controller():
        log.debug("Starting dijkstra controller...")
        core.registerNew(DijkstraController)

    core.call_when_ready(start_controller, "openflow_discovery")
