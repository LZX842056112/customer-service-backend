from atguigu.domain.state import DialogueState
from atguigu.task.flow.flows import FlowsList
from atguigu.task.command.commands import Command, StartedFlowCommand, ResumedFlowCommand, CancelFlowCommand, \
    SetSlotsCommand
from atguigu.domain.contexts import StartedSystemContext, InterruptedSystemContext, CanceledSystemContext, \
    ResumedSystemContext, TaskContext


class CommandProcessor:
    """
    命令处理器
    作用：处理四种命令：
    StartFlowCommand: 我想查询订单状态---LLM根据自然语言【任务】以及提示词上下文----{"command":"start_flow": flow:"flow_id"}----【结构化的数据模型StartFlowCommand】
    ---->开启业务流程(应用) 开启业务流程（state.active_task） 开启一个开始的系统流程 state.active_system_task
    ResumedFlowCommand: 我想继续开始订单状态查询 -----  {"command": "resume_flow"}  {"command": "resume_flow", "flow": "flow_id"}
    CancelFlowCommand: 我不想开始订单状态查询-----{"command":"cancel_flow"}
    SetSlotsCommand: 我的订单号是A10001-----{"command":"set_slots","slots":{"slot_name":""}}


    """

    def run(self,
            state: DialogueState,
            flow_list: FlowsList,
            commands: list[Command]):

        for command in commands:
            self._apply(command, state, flow_list)

    def _apply(self,
               command: Command,
               state: DialogueState,
               flow_list: FlowsList
               ):
        """
        判断具体的command类型是哪一种
        :param command:
        :return:
        """
        if isinstance(command, StartedFlowCommand):
            self._process_start_flow(command, state, flow_list)
        elif isinstance(command, SetSlotsCommand):
            self._process_slots_fill(command, state)
        elif isinstance(command, ResumedFlowCommand):  # 交给你TODO
            self._process_resume_flow(command, state, flow_list)
        elif isinstance(command, CancelFlowCommand):
            self._process_cancel_flow(state, flow_list)
        else:
            pass

    def _process_slots_fill(self,
                            command: SetSlotsCommand,
                            state: DialogueState):
        """
        职责： 将command的slots获取出来，设置到当期业务流程上下文的slots属性
        :param command:
        :param state:
        :return:
        """
        state.set_slots(command.slots)  # 一行代码

    def _process_cancel_flow(self,
                             state: DialogueState,
                             flow_list: FlowsList):
        """
        职责：
        1. 激活取消系统流程的开场白
        2. 清空所有流程(业务流程以及系统流程)
        :param command:
        :param state:
        :param flow_list:
        :return:
        """

        # 1. 获取取消系统流程对象以及开始步骤的步骤ID
        cancel_system_flow = flow_list.get_flow_by_id("system_task_canceled")
        start_step_id = cancel_system_flow.get_start_step().id

        # 2. 获取当前正在执行的业务流程(流程ID以及流程名字)
        active_task = state.active_task
        canceled_flow_id = active_task.flow_id
        canceled_flow_name = flow_list.get_flow_by_id(canceled_flow_id).flow_name

        # 3. 清空所有流程(业务流程、系统流程都清空)
        state.end_activating_task()

        # 4. 激活取消系统流程
        state.start_active_system_task(CanceledSystemContext(
            flow_id="system_task_canceled",
            step_id=start_step_id,
            canceled_flow_id=canceled_flow_id,  # 取消业务流程的流程ID
            canceled_flow_name=canceled_flow_name  # 取消业务流程的流程名字

        ))

    def _process_start_flow(self,
                            command: StartedFlowCommand,
                            state: DialogueState,
                            flow_list: FlowsList):
        """
        职责：激活指定业务流程、激活开始系统流程
        :param command:
        :param state:
        :param flow_list:
        :return:
        """

        # 1. 清空之前的系统流程：(过长白)【不能清空之前业务流程：存起来】
        state.end_activating_system_task()

        # 1.1 获取开启业务流程ID
        start_flow_id = command.flow
        # 1.2 获取开启业务流程
        start_business_flow = flow_list.get_flow_by_id(start_flow_id)

        # 2. 判断当前是否存在正在运行的业务流程
        active_task = state.active_task

        # 2.1 当前有正在运行的业务流程
        if active_task is not None:

            # a) 当前正在运行的业务流程刚好是要开启的业务流程
            if active_task.flow_id == start_flow_id:
                return  # 什么都不做

            # b) 中断当前正在执行的业务流程(当前正在执行的业务流程不等于要开启的业务流程)
            interrupted_flow_id = active_task.flow_id
            interrupted_flow_name = flow_list.get_flow_by_id(interrupted_flow_id).flow_name
            state.interrupted_activating_task()

            # c) 从暂停栈中在查询一次
            if not state.resumed_interrupted_business_task(flow_id=start_flow_id):
                state.start_active_business_task(TaskContext(
                    flow_id=start_flow_id,  # 开启业务流程的流程ID
                    step_id=start_business_flow.get_start_step().id
                ))

            # d) 激活中断的系统流程(不管业务流程要不要激活(创建)，都需要激活中断系统流程。)
            interrupted_system_flow = flow_list.get_flow_by_id("system_task_interrupted")
            state.start_active_system_task(InterruptedSystemContext(
                flow_id="system_task_interrupted",
                step_id=interrupted_system_flow.get_start_step().id,
                interrupted_flow_id=interrupted_flow_id,
                interrupted_flow_name=interrupted_flow_name,
                started_flow_id=start_flow_id,
                started_flow_name=start_business_flow.flow_name
            ))

        # 2.2 当前没有运行的业务流程
        else:
            # a) 从暂停栈中在查询一次,如果查询到了当前要开启的业务流程，不用开启业务流程，不用开启开始的系统流程（这个开场白之前已经说过一次）恢复开场白表示出来
            if state.resumed_interrupted_business_task(flow_id=start_flow_id):
                resumed_system_flow = flow_list.get_flow_by_id("system_task_resumed")
                active_task = state.active_task
                state.start_active_system_task(ResumedSystemContext(
                    flow_id="system_task_resumed",
                    step_id=resumed_system_flow.get_start_step().id,
                    resumed_flow_id=active_task.flow_id,
                    resumed_flow_name=flow_list.get_flow_by_id(active_task.flow_id).flow_name
                ))
                return

            # b) 从暂停栈中未查询到当前要开启的业务流程
            # 1. 激活当前业务流程
            state.start_active_business_task(TaskContext(
                flow_id=start_flow_id,  # 开启业务流程的流程ID
                step_id=start_business_flow.get_start_step().id
            ))
            # 2. 激活开始系统流程
            start_system_flow = flow_list.get_flow_by_id("system_task_started")
            state.start_active_system_task(
                StartedSystemContext(
                    flow_id="system_task_started",
                    step_id=start_system_flow.get_start_step().id,
                    started_flow_id=start_flow_id,
                    started_flow_name=start_business_flow.flow_name
                )
            )

    def _process_resume_flow(self,
                             command: ResumedFlowCommand,
                             state: DialogueState,
                             flow_list: FlowsList):
        """
        职责： 恢复中断的业务流程(指定的业务流程和最近的业务流程)
        场景：我准备继续执行订单状态查询-----{"command":"resumed_tas",flow="order_status"}  --- ResumedFlowCommand的flow值order_status
        场景：我继续回到上一次-----{"command":"resumed_tas"}--- ResumedFlowCommand的flow值order_status的值None:----从栈顶获取最近中断的业务流程
        :param command:
        :param state:
        :param flow_list:
        :return:
        """

        # 1. 获取要恢复的业务流程的流程ID
        resumed_flow_id = command.flow

        # 2. 如果resumed_flow_id是None 且栈中没有任何元素(流程)
        if resumed_flow_id is None and not state.interrupted_active_tasks:
            return

        # 3. resumed_flow_id 不为空或者resumed_flow_id为空但是栈中有元素（流程）
        # 3.1 获取当前正在执行的业务流程
        active_task = state.active_task
        # 3.1 当前是存在正在执行的流程
        if active_task is not None:
            # a) 要恢复的业务流程流程ID (先获取指定的业务流程ID 如果不存在获取栈顶的流程)
            resumed_flow_id = resumed_flow_id or state.interrupted_active_tasks[-1].flow_id

            # b) 当前正在执行的业务流程ID等于要恢复的业务流程ID
            if active_task.flow_id == resumed_flow_id:
                return  # 不需要恢复(恢复系统流程的开场白都不用提示)

            # c)  当前正在执行的业务流程ID不等于要恢复的业务流程ID
            interrupted_flow_id = active_task.flow_id
            interrupted_flow_name = flow_list.get_flow_by_id(interrupted_flow_id).flow_name
            state.interrupted_activating_task()  # 中断正在执行的业务流程
            if not state.resumed_interrupted_business_task(flow_id=resumed_flow_id):
                state.resumed_interrupted_business_task()  # 撤销之前正在执行的业务流程

                return

            # d ) 激活中断的系统流程
            interrupted_system_flow = flow_list.get_flow_by_id("system_task_interrupted")
            state.start_active_system_task(InterruptedSystemContext(
                flow_id="system_task_interrupted",
                step_id=interrupted_system_flow.get_start_step().id,
                interrupted_flow_id=interrupted_flow_id,
                interrupted_flow_name=interrupted_flow_name,
                started_flow_id=resumed_flow_id,
                started_flow_name=flow_list.get_flow_by_id(resumed_flow_id).flow_name
            ))
        else:
            if not state.resumed_interrupted_business_task(flow_id=resumed_flow_id):
                return
            # 激活恢复系统流程
            resumed_system_flow = flow_list.get_flow_by_id("system_task_resumed")
            resumed_task = state.active_task
            state.start_active_system_task(ResumedSystemContext(
                flow_id="system_task_resumed",
                step_id=resumed_system_flow.get_start_step().id,
                resumed_flow_id=resumed_task.flow_id,  # 恢复业务流程的流程ID
                resumed_flow_name=flow_list.get_flow_by_id(resumed_task.flow_id).flow_name  # 恢复业务流程的流程名字
            ))
