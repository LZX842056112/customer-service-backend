from dataclasses import dataclass


@dataclass(slots=True)
class FlowStepLink:
    """
    边的基类: 提供下一个step_id
    """
    target: str  # 下一个步骤的ID(下一个step地址)


@dataclass(slots=True)
class FlowStepStaticLink(FlowStepLink):
    """
    next: ask_refund_reason
    """
    pass


@dataclass(slots=True)
class FlowStepConditionLink(FlowStepLink):
    """
    next:
            - if: "context.get('reason') == 'clarification_rejected'"
            then: clarification_rejected
            ....
    """
    condition: str  # "context.get('reason') == 'clarification_rejected" eval()计算


@dataclass(slots=True)
class FlowStepFallbackLink(FlowStepLink):
    """
    next:
          - else: ask_rephrase
    """
    pass
