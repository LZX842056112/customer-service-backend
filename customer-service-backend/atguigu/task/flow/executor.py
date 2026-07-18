from dataclasses import asdict

from atguigu.domain.messages import BotMessage
from atguigu.domain.state import DialogueState
from atguigu.task.action.base import ActionCall, ActionResult
from atguigu.task.action.runner import ActionRunner
from atguigu.task.flow.flows import FlowsList
from atguigu.task.flow.links import FlowStepStaticLink, FlowStepFallbackLink, FlowStepConditionLink
from atguigu.task.flow.steps import FlowStep, StartFlowStep, EndFlowStep, ActionFlowStep, CollectFlowStep
from atguigu.domain.contexts import CollectedSystemContext


class FlowExecutor:
    async def execute_flow(self,
                           state: DialogueState,
                           flow_list: FlowsList,
                           action_runner: ActionRunner) -> list[BotMessage]:
        """
          流程推进器
          职责：推进yaml流程【业务流程、系统流程】，如果遇到流程的step类型action且名字action_listener（system_collect_information）,此时流程推进器就不能继续往下推
          :param state:
          :param flow_list:
          :param action_runner:
          :return:
        """
        final_messages = []
        while True:  # 负责:流程的步骤类型是action类型
            # 1. 推进流程，找到流程的某一步类型是action
            action_call: ActionCall = self._advance_flow_util_action(state, flow_list)

            # 2. 判断action
            if action_call.action_name == "action_listen":
                break
            else:
                # a) action_name:action_response:响应 b) action_xxx:调用第三方接口
                action_result: ActionResult = await action_runner.run(action_call, state)
                final_messages.extend(action_result.messages)  # action_response返回的内容 获取到
                state.set_slots(action_result.slot_updates)  # action_xxx返回业务需要的其它槽位获取到

        # 3. 收集到的返回出去
        return final_messages

    def _advance_flow_util_action(self,
                                  state: DialogueState,
                                  flow_list: FlowsList) -> ActionCall:
        """
        推进流程（沿着边(link)---执行节点（step))
        职责：负责管step
        :param state:
        :param flow_list:
        :return:
        """

        while True:

            # 1. 获取当前正在执行的流程(上下文)(系统流程、业务流程)
            current_activating_task = state.current_activating_task()

            if current_activating_task is None:
                return ActionCall(action_name="action_listen")

            # 2. 从上下文中获取正在执行的流程ID
            flow_id = current_activating_task.flow_id

            # 3. 根据当前流程的流程ID 获取流程对象
            flow = flow_list.get_flow_by_id(flow_id)

            # 4. 获取流程的步骤对象
            step = flow.get_step_by_id(current_activating_task.step_id)

            action_call: ActionCall | None = self._run_step(state, step, flow_list)

            # 5. action_call 返回
            if action_call is not None:
                return action_call

    def _run_step(self,
                  state: DialogueState,
                  step: FlowStep,
                  flow_list: FlowsList) -> ActionCall | None:
        """
        运行流程的某一步
        :param state:
        :param step:
        :param flow_list:
        :return:
        """

        if isinstance(step, StartFlowStep):
            return self._run_start_step(state, step)
        elif isinstance(step, EndFlowStep):
            return self._run_end_step(state)
        elif isinstance(step, ActionFlowStep):
            return self._run_action_step(state, step)
        elif isinstance(step, CollectFlowStep):
            return self._run_collect_step(state, step, flow_list)
        else:
            pass

    def _run_start_step(self,
                        state: DialogueState,
                        step: StartFlowStep) -> None:
        """
        职责：更新step_id即可（state.current_activating_task().step_id）没有业务逻辑
        :param state:
        :param step:
        :return:
        """

        # 1. 推进step
        self._advance_flow_step(state, step)

        # 2. 返回None
        return None

    def _advance_flow_step(self, state: DialogueState, step: FlowStep):

        # 1. 找到step_id
        step_id: str = self._select_step_id(state, step)

        # 2. 更新step_id到当前正在运行的上下文对应的(系统、业务)流程，保证内层循环可以自动把一个step执行完之后 执行到下一个step中
        state.current_activating_task().step_id = step_id

    def _select_step_id(self, state: DialogueState, step: FlowStep) -> str:
        """
        找一个step_id
        :param step:
        :return:
        """

        for link in step.next:
            if isinstance(link, FlowStepStaticLink):
                return link.target  # 下一个step_id

            if isinstance(link, FlowStepFallbackLink):
                return link.target  # 下一个step_id

            if isinstance(link, FlowStepConditionLink):  # 不会执行到 扩展的system_cannot_handle才有条件边
                if self._eval_condition(state, link.condition):
                    return link.target

        return "not exist  link"  # 走不到

    def _eval_condition(self,
                        state: DialogueState,
                        condition: str,
                        ) -> bool:
        """
        计算条件(边条件 槽位条件)
        "context.get('reason') == 'clarification_rejected'"
        :param condition:
        :return:

         eval(param1,param2,param3)
         param1:条件表达式
         param2: 全局变量---禁用掉
         param3: 局部变量
        """
        data = {
            "slots": state.active_task.slots,  # 支持条件表达式中可以写入变量叫slots （可选的支开关支持）
            "context": asdict(state.active_system_task)
        }
        return eval(condition, {}, data)

    def _run_end_step(self, state: DialogueState) -> None:
        """
        职责： 判断当前系统流程是否执行完 以及业务流程是否执行完
        :param state:
        :return:
        """
        if state.active_system_task:
            state.end_activating_system_task()
        elif state.active_task:
            state.end_activating_task()
        else:
            pass

        return None

    def _run_action_step(self,
                         state: DialogueState,
                         step: ActionFlowStep) -> ActionCall:

        # 1. 推进下一步
        self._advance_flow_step(state, step)

        # 2. 构建action_call
        return self._build_action_call(state, step)

    def _build_action_call(self, state, step):
        # 1. 获取action_name
        action_name = step.action

        # 2. action_args
        action_kwargs = step.args
        if isinstance(action_kwargs, str):
            # context.response    #    text: "请告诉我你的订单号。"
            action_kwargs = asdict(state.active_system_task)[action_kwargs.split(".")[1]]
        return ActionCall(action_name=action_name, action_kwargs=action_kwargs)

    def _run_collect_step(self,
                          state: DialogueState,
                          step: CollectFlowStep,
                          flow_list: FlowsList):
        """
        注意：进入两次:第一次做完一定要返回None(内部循环推荐下一步step 才能继续) 且不能更新step_id（执行下一步去了）
        1. 第一次触发：system_collect_information系统流程进行槽位收集
        2. 第二次触发：对填写槽位的校验(用户主动填写，填写的不合法...)
        :param state:
        :param step:
        :param flow_list:
        :return:
        """
        self._try_to_fill_slot_from_focused_object(state,step)
        if state.active_task.slots.get(step.slot_name):
            # 第二次触发(槽位信息填写过：LLM/点击卡片)
            if step.validate:
                # 校验通过
                if self._eval_condition(state, step.validate.condition):
                    self._advance_flow_step(state, step)
                    return None
                # 校验失败 重新在填写一遍【重新触发了收集信息的系统流程】错误的信息
                else:
                    state.remove_slot(step.slot_name)  # 移除掉填错的槽位信息
                    if step.validate.failure_response:
                        return ActionCall(action_name="action_response",
                                          action_kwargs=asdict(step.validate.failure_response))
                    else:
                        return ActionCall(action_name="action_response",
                                          action_kwargs={"text": "你填写的信息的有误，请您重新输入!"})
            else:
                # 推荐下一步
                self._advance_flow_step(state, step)
                return None
        else:
            # 第一次触发(激活收集信息的系统流程 等用户填写槽位信息)
            state.start_active_system_task(CollectedSystemContext(
                flow_id="system_collect_information",
                step_id=flow_list.get_flow_by_id("system_collect_information").get_start_step().id,
                response=asdict(step.response),
                slot_name=step.slot_name
            ))
            return None

    def _try_to_fill_slot_from_focused_object(self, state: DialogueState, step: CollectFlowStep):
        if state.focused_object is None:
            return
        if step.slot_name == 'order_number' and state.focused_object.type == "order":
            state.set_slots({step.slot_name: state.focused_object.id})
        if step.slot_name == "product_id" and state.focused_object.type == "product":
            state.set_slots({step.slot_name: state.focused_object.id})


if __name__ == '__main__':
    condtion_str = "context.get('reason') == 'clarification_rejected'"
    data = {
        "context": {
            "reason": "clarification_rejected"
        },
        "slots": {
            "order_number": "A10001"
        }

    }
    print(eval(condtion_str, {}, data))
