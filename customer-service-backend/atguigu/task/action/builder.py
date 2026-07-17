import importlib
import inspect
import pkgutil

from atguigu.task.action.base import Action
from atguigu.task.action.builtin.listener import ActionListener
from atguigu.task.action.builtin.response import ActionResponse
from atguigu.task.action.register import ActionRegister
from atguigu.task.action.runner import  ActionRunner

def register_builtin_actions(action_runner: ActionRunner):
    """
    内置的两个Action注册到ActionRunner的注册中心
    :param action_runner:
    :return:
    """
    action_runner.registry.register(ActionResponse())
    action_runner.registry.register(ActionListener())

def register_custom_actions(action_runner: ActionRunner):
    package = importlib.import_module("atguigu.task.action.customer")

    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."):
        if is_pkg:
            continue
        module = importlib.import_module(module_name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, Action) or obj is Action:
                continue
            if obj.__module__ != module.__name__:
                continue
            action_runner.registry.register(obj())




def build_action_runner() -> ActionRunner:
    action_runner = ActionRunner(ActionRegister())
    register_builtin_actions(action_runner)
    register_custom_actions(action_runner)
    return action_runner



















