from pox.core import core
from pox.openflow.of_01 import ConnectionUp
from pox.lib.revent import EventMixin
from pox.openflow.discovery import LinkEvent

from swarmsdn.graph import NetGraph

log = core.getLogger()


class GraphControllerBase(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        self.listenTo(core.openflow_discovery)
        core.openflow_discovery.addListeners(self)
        self.graph = NetGraph()

    def hook_handle_connetion_up(self, event: ConnectionUp):
        """
        Override in child classes to implement additional connection up behaviour
        """
        pass

    def hook_handle_link_event(self, event: LinkEvent):
        """
        Override in child classes to implement additional link event behaviour
        """
        pass

    def _handle_LinkEvent(self, event: LinkEvent):
        # test that discovery works
        log.debug("======LINK EVT========")
        self.graph.update_from_linkevent(event)
        self.hook_handle_link_event(event)

    def _handle_ConnectionUp(self, event: ConnectionUp):
        log.debug("=========== SW UP EVT ===========")
        self.graph.register_node(event.dpid)
        self.hook_handle_connetion_up(event)
