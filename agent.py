from utils import *
from config import *
from prompt import *

import os
from langchain.chains import LLMChain,LLMRequestsChain
from langchain.prompts import PromptTemplate
from langchain.vectorstores.chroma import Chroma
from langchain.vectorstores.faiss import FAISS
from langchain.schema import Document
from langchain.agents import ZeroShotAgent,AgentExecutor,Tool
from langchain.memory import ConversationBufferMemory
from langchain.output_parsers import ResponseSchema,StructuredOutputParser

class Agent():
    def __init__(self):
        self.vdb=Chroma(
            persist_directory=os.path.join(os.path.dirname(__file__),'./data/db'),
            embedding_function=get_embeddings_model()
        )

    def generic_func(self,query):
        prompt=PromptTemplate.from_template(GENERIC_PROMPT_TPL)
        llm_chain=LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        return llm_chain.run(query)

    #填充提示词并总结答案
    def retrival_func(self,query):
        documents=self.vdb.similarity_search_with_relevance_scores(query,k=5)
        # print(documents)
        # exit()
        query_result=[doc[0].page_content for doc in documents if doc[1]>0.7]
        prompt=PromptTemplate.from_template(RETRIVAL_PROMPT_TPL)
        retrival_chain=LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        inputs={
            'query':query,
            'query_result':'\n\n'.join(query_result) if len(query_result) else '没有查到'
        }
        return retrival_chain.run(inputs)


if __name__=='__main__':
    agent=Agent()
    # print(agent.generic_func('你叫什么名字？'))
    print(agent.retrival_func('介绍一下寻医问药网'))
    print(agent.retrival_func('寻医问药网的客服电话是多少？'))