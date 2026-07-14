from pathlib import Path

from atguigu.engine.dialogue_engine import DialogueEngine
from atguigu.plan.planner import TurnPlanner
from atguigu.task.handler import TaskHandler
from atguigu.knowledge.handler import KnowledgeHandler
from atguigu.plan.validator import TurnPlanValidator
from atguigu.chitchat.handler import ChitChatHandler
from atguigu.task.flow.loader import FlowLoader
from atguigu.knowledge.intents import KNOWLEDGE_INTENTS
from atguigu.clarify.responder import ClarifyResponser

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]
FLOW_CONFIG_DIR = PROJECT_ROOT_DIR / "flow_config"
FLOW_CONFIG_FILE = ["system_flows.yml", "user_flows.yml"]


def build_dialogue_engine():
    flow_list = FlowLoader().load_many_yaml(
        [FLOW_CONFIG_DIR / file for file in FLOW_CONFIG_FILE])  # flow_list是两个yml中的流程(系统流程、业务流程)

    return DialogueEngine(
        planner=TurnPlanner(),
        task_handler=TaskHandler(flow_list=flow_list),
        turn_plan_validator=TurnPlanValidator(),
        knowledge_handler=KnowledgeHandler(intents=KNOWLEDGE_INTENTS),
        chitchat_handler=ChitChatHandler(),
        clarify_responder=ClarifyResponser()

    )
