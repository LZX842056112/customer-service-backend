from pathlib import Path


def load_prompt_template(prompt_template_nam: str) -> str:
    """
    根据模版引擎的名字
    :param prompt_template_nam:
    :return:
    """

    file_path = Path(__file__).resolve().parents[0] / "jinja2" / f"{prompt_template_nam}.jinja2"

    return file_path.read_text(encoding="utf-8")
