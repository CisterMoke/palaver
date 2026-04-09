from loguru import logger

from palaver.app.event_handlers.base import BaseEventHandler
from palaver.app.events.agent import AgentFinishedEvent, SendAgentEvent, AwaitAgentEvent


class AwaitTracker:
    class TrackItem:
        def __init__(self, event: AwaitAgentEvent):
            self.event = event
            self.subagent_run_ids: set[str] = set()
            self.results: list[str] = []

    def __init__(self):
        self.track_record: dict[str, 'AwaitTracker.TrackItem'] = dict()

    def track_new(self, event: AwaitAgentEvent):
        logger.debug(f"Tracking new AwaitAgentEvent '{event.run_id}'")
        self.track_record[event.run_id] = self.TrackItem(event)

    def register_send_event(self, event: SendAgentEvent):
        if event.awaited_by is None:
            return
        
        self.track_record[event.awaited_by].subagent_run_ids.add(event.run_id)

        logger.debug(f"Registering new SendAgentEvent for '{event.awaited_by}'")
        logger.debug(f"Awaiting replies from '{len(self.track_record[event.awaited_by].subagent_run_ids)}' agents.")

    def collect_reply(self, event: AgentFinishedEvent):
        if event.awaited_by is None:
            return
        
        item = self.track_record[event.awaited_by]
        item.results.append(event.result)
        item.subagent_run_ids.remove(event.run_id)

        logger.debug(f"Registering reply for '{event.awaited_by}'")
        logger.debug(f"Awaiting replies from '{len(self.track_record[event.awaited_by].subagent_run_ids)}' agents.")

        if len(item.subagent_run_ids) == 0:
            logger.debug(f"Setting final result for '{event.awaited_by}'")

            final_result = "\n\n".join(item.results)
            item.event.set_result(final_result)
            self.track_record.pop(event.awaited_by)

            logger.debug(f"Final Result: {final_result}")


class CoreEventHandler(BaseEventHandler):
    def __init__(self):
        self._await_tracker = AwaitTracker()

    async def handle_event(self, event):
        if isinstance(event, AwaitAgentEvent):
            self._await_tracker.track_new(event)
        elif isinstance(event, SendAgentEvent):
            self._await_tracker.register_send_event(event)
        elif isinstance(event, AgentFinishedEvent):
            self._await_tracker.collect_reply(event)
