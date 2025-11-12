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

    #命名实体识别
    def graph_func(self,query):
        response_schemas=[
            ResponseSchema(type='list', name='disease', description='疾病名称实体'),
            ResponseSchema(type='list', name='symptom', description='疾病症状实体'),
            ResponseSchema(type='list', name='drug', description='药品名称实体'),
        ]
        output_parser=StructuredOutputParser(response_schemas=response_schemas)
        # format_instructions=structured_output_parser(response_schemas)  这个用不了！！！
        format_instructions = output_parser.get_format_instructions()

        ner_prompt=PromptTemplate(
            template=NER_PROMPT_TPL,
            partial_variables={'format_instructions':format_instructions},
            input_variables=['query']
        )
        ner_chain=LLMChain(
            llm=get_llm_model(),
            prompt=ner_prompt,
            verbose=os.getenv('VERBOSE')
        )
        result=ner_chain.run({
                'query':query
            })
        ner_result=output_parser.parse(result)
        print(ner_result)


if __name__=='__main__':
    agent=Agent()
    # print(agent.generic_func('你叫什么名字？'))
    # print(agent.retrival_func('介绍一下寻医问药网'))
    # print(agent.retrival_func('寻医问药网的客服电话是多少？'))
    print(agent.graph_func('感冒一般是什么引起的？'))
    print(agent.graph_func('感冒吃什么药好得快？可以吃阿莫西林吗？'))
