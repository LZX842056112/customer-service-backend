import yaml
from typing import Any
from pathlib import Path
from atguigu.task.flow.flows import FlowsList, FlowSlot, Flow, FlowStep
from atguigu.task.flow.steps import CollectFlowStep

class FlowLoader:

    def load_many_yaml(self, paths: list[str | Path]) -> FlowsList:
        flows: list[Flow] = []
        slots: dict[str, FlowSlot] = {}
        for path in paths:
            loaded = self.load_yaml(path)
            flows.extend(loaded.flows)
            slots.update(loaded.slots)
        return FlowsList(flows=flows, slots=slots)

    def load_yaml(self, path: Path) -> FlowsList:
        # 1. 读取yaml文件加载为dict对象
        with open(path, 'r', encoding='utf-8') as f:
            dict_data = yaml.safe_load(f)

        # 2. 加载slots
        loaded_slots: dict[str, FlowSlot] = self.load_slots(dict_data.get('slots', {}))

        # 3. 加载flows
        loaded_flows: list[Flow] = self.load_flows(dict_data.get('flows', {}), loaded_slots)

        return FlowsList(slots=loaded_slots, flows=loaded_flows)

    def load_slots(self, slots: dict[str, Any]) -> dict[str, FlowSlot]:
        """
        加载yaml中的slots
        将槽位的字典对象转成FlowSlot对象
        :param slots:
        :return:
        dict[str,FlowSlot]
        """
        loaded_slots: dict[str, FlowSlot] = {}

        for slot_name, slot_dict in slots.items():
            loaded_slots[slot_name] = FlowSlot(name=slot_name,
                                               type=slot_dict.get('type'),
                                               label=slot_dict.get('label'),
                                               description=slot_dict.get('description'))

        return loaded_slots

    def load_flows(self, flows: dict[str, Any], loaded_slots: dict[str, FlowSlot]) -> list[Flow]:
        """
        加载yaml中的flows
        :param flows:
        :param loaded_slots:
        :return:
        """

        loaded_flows: list[Flow] = []

        for flow_id, flow_dict in flows.items():
            steps: list[FlowStep] = [FlowStep.from_dict(step_dict) for step_dict in flow_dict.get('steps', [])]
            loaded_flows.append(
                Flow(
                    flow_id=flow_id,
                    flow_name=flow_dict.get('name'),
                    description=flow_dict.get('description'),
                    steps=steps,
                    slots=self._load_flow_slot(steps, loaded_slots)

                )
            )

        return loaded_flows

    def _load_flow_slot(self, steps: list[FlowStep], loaded_slots: dict[str, FlowSlot]) -> dict[str, FlowSlot]:
        """

        :param steps:
        :param loaded_slots:
        :return:
        """

        seen = set()
        flow_slots: dict[str, FlowSlot] = {}
        for step in steps:

            if not isinstance(step, CollectFlowStep):
                continue
            # 1. 获取到流程的槽位名字
            flow_slot_name = step.slot_name

            # 2. 校验该槽位是否有定义
            slot_definition = loaded_slots.get(flow_slot_name)

            if slot_definition is not None:
                flow_slots[flow_slot_name] = slot_definition

        return flow_slots


if __name__ == '__main__':
    yaml_path = Path(__file__).resolve().parents[2] / "flow_config" / "system_flows.yml"

    flow_loader = FlowLoader()

    flow_loader.load_yaml(path=yaml_path)
