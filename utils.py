from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from py2neo import Graph
from config import *

import os
from dotenv import load_dotenv
load_dotenv()

def get_embeddings_model():
    model_map = {
        'openai': OpenAIEmbeddings(
            model = os.getenv('OPENAI_EMBEDDINGS_MODEL')
        )
    }
    return model_map.get(os.getenv('EMBEDDINGS_MODEL'))


def get_llm_model():
    model_map = {
        'openai': ChatOpenAI(
            model = os.getenv('OPENAI_LLM_MODEL'),
            temperature = os.getenv('TEMPERATURE'),
            max_tokens = os.getenv('MAX_TOKENS'),
            openai_api_base=os.getenv('OPENAI_API_BASE'),  # 注意参数名是 openai_api_base
            openai_api_key=os.getenv('OPENAI_API_KEY')  # 注意参数名是 openai_api_key
        )
    }
    return model_map.get(os.getenv('LLM_MODEL'))

#json输出格式化函数
def structured_output_parser(response_schemas):
    text = '''
    请从以下文本中，抽取出实体信息，并按json格式输出，json包含首尾的 "``" json" 和 "``"
    。
    以下是字段含义和类型，要求输出json中，必须包含下列所有字段：\n
    '''
    for schema in response_schemas:
        text += schema.name + ' 字段，表示：' + schema.description + '，类型为：' + schema.type + '\n'
    return text

#文本替换函数
def replace_token_in_string(string,slots):
    for key,value in slots:
        string=string.replace('%'+key+'%',value)
    return string

if __name__ == '__main__':
    llm_model=get_llm_model()
    print(llm_model.predict('感冒吃什么食物有助于恢复？'))