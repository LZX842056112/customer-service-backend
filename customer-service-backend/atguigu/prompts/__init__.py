"""
电商小二用的提示模版都是采用jinja2模版引擎提供的。---模版引擎：本质是文本+{{}}这种格式    LangChain:提示词模版中{}---f-string
jinja2的模版引擎：langchain默认提供解析方式。
"""
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import  JsonOutputParser

if __name__ == '__main__':
    prompt_template = PromptTemplate.from_template(template="这是我的{{name}}",template_format="jinja2")

    print(prompt_template.invoke({"name": "tom"}))


    json_out_put_parser=JsonOutputParser()

    json_out_put_parser.invoke()
