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

if __name__ == '__main__':
    llm_model=get_llm_model()
    print(llm_model.predict('感冒吃什么食物有助于恢复？'))