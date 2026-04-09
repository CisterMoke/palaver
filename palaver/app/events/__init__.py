from palaver.app.events.agent import AgentFinishedEvent, SendAgentEvent, AwaitAgentEvent
from palaver.app.events.ui import UIEvent


Event = SendAgentEvent | AwaitAgentEvent | AgentFinishedEvent | UIEvent