from atguigu.plan.turn_plan import TurnPlanValidateResult, TurnPlan, ClarifyReason
from atguigu.domain.state import DialogueState
from atguigu.task.flow.flows import FlowsList
from atguigu.task.command.commands import StartedFlowCommand, CancelFlowCommand, ResumedFlowCommand, SetSlotsCommand
from atguigu.knowledge.intents import KnowledgeIntent


class TurnPlanValidator:
    def validate(self,
                 turn_plan: TurnPlan,
                 state: DialogueState,
                 flow_list: FlowsList,
                 intents: dict[str, KnowledgeIntent]
                 ) -> TurnPlanValidateResult:
        """
        分为两大校验类型
        校验外层轨道数【一条轨道没命中、命中了多条轨道】
        校验内层的轨道约束【校验业务轨道、知识检索轨道】闲聊轨道不校验
        :param turn_plan:
        :param state:
        :return:
        """

        # 1. 获取turn_plan中的轨道数
        selected_tracks = turn_plan.activated_tracks()

        # 2. 校验轨道是否未命中
        if not selected_tracks:
            return self.reject(reason=ClarifyReason.MISSING_TRACK)

        # 3. 校验轨道是否命中了多条
        if len(selected_tracks) > 1:
            return self.reject(reason=ClarifyReason.MULTIPLE_TRACKS)

        # 4. 校验唯一的那一条轨道
        selected_track = selected_tracks[0]

        # 4.1 校验任务轨道
        if selected_track == "task":
            return self._validate_task_track(turn_plan, flow_list)

        # 4.2 校验知识检索轨道
        elif selected_track == "knowledge":
            return self._validate_knowledge_track(turn_plan,state, intents)

        # 4.3 闲聊轨道(真实公司中不允许闲聊)
        return TurnPlanValidateResult(valid=True)

    def reject(self, reason: ClarifyReason) -> TurnPlanValidateResult:
        return TurnPlanValidateResult(valid=False, reason=reason)

    def _validate_task_track(self,
                             turn_plan: TurnPlan,
                             flow_list: FlowsList) -> TurnPlanValidateResult:
        """
        四重校验(TODO 众多的校验--->扩展点)
        1. 校验commands(是否有对应的命令)是否存在
        2. 校验commands中各个command的类型(白名单机制)
        3. 校验是否存在多个StartedFlowCommand(开启多个业务流程)
        4. 校验业务流程是否存在(根据流程ID 找流程)
        :param turn_plan:
        :return:
        """
        task_track = turn_plan.task

        # 1. 校验一：校验commands是否存在
        if not task_track.commands:
            return self.reject(reason=ClarifyReason.MISSING_TASK_COMMANDS)

        # 2.校验二：检验command的类型
        allowed_command = (StartedFlowCommand, CancelFlowCommand, ResumedFlowCommand, SetSlotsCommand)
        if not all(isinstance(command, allowed_command) for command in task_track.commands):
            return self.reject(reason=ClarifyReason.INVALID_TASK_COMMANDS)

        # 3. 校验三: 校验多个StartedFlowCommand
        started_flow_cmd = [start_cmd for start_cmd in task_track.commands if isinstance(start_cmd, StartedFlowCommand)]
        if len(started_flow_cmd) > 1:
            return self.reject(reason=ClarifyReason.MULTIPLE_TASK_FLOWS)

        # 4. 4.1 有且只有一个StartedFlowCommand 4.2 一个都没有(单独给一个SetSlowsCommand/CancelFlowCommand/ResumedFlowCommand)
        if started_flow_cmd:
            started_cmd = started_flow_cmd[0]
            flow_id = started_cmd.flow
            flow = flow_list.get_flow_by_id(flow_id)
            if flow is None:
                return self.reject(reason=ClarifyReason.UNKNOWN_TASK_FLOW)

        return TurnPlanValidateResult(valid=True)

    def _validate_knowledge_track(self,
                                  turn_plan:TurnPlan,
                                  state: DialogueState,
                                  intents: dict[str, KnowledgeIntent]):

        """
        校验规则：LLM输出的知识意图intents:["product_info","order_info"]是否是知识意图表中的(商品信息查询或者订单信息查询。)
        :param state:
        :param intents:
        :return:
        """

        knowledge_plan = turn_plan.knowledge


        if not knowledge_plan.intents:
            return self.reject(ClarifyReason.MISSING_KNOWLEDGE_INTENT)

        focused_object = state.focused_object
        for intent in knowledge_plan.intents:
            intent_meta = intents[intent]
            required_object = intent_meta.requires_object
            if required_object is not None:
                if focused_object is None or focused_object.type != required_object:
                    return self.reject(ClarifyReason.MISSING_FOCUSED_OBJECT)

        return TurnPlanValidateResult(valid=True)






