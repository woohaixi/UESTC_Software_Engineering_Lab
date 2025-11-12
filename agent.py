from sqlalchemy.testing.suite.test_reflection import metadata

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
        # print(ner_result)

        #命名实体识别结果，填充模板
        graph_templates=[]
        for key,template in GRAPH_TEMPLATE.items():
            slot=template['slots'][0]#slot是占位符的名称，比如这个例子里的disease
            slot_values=ner_result[slot]#slot_values在这个例子里是感冒，鼻炎
            # print(slot,slot_values)
            # exit()
            for value in slot_values:
                graph_templates.append({
                    'question':replace_token_in_string(template['question'],[[slot,value]]),
                    'cypher':replace_token_in_string(template['cypher'],[[slot,value]]),
                    'answer':replace_token_in_string(template['answer'],[[slot,value]]),
                })
        # print(graph_templates)
        if not graph_templates:
            return

        #计算问题相似度，筛选最相关问题
        graph_documents=[
            Document(page_content=template['question'],metadata=template)
            for template in graph_templates
        ]
        # print(graph_documents)
        # exit()
        db=FAISS.from_documents(graph_documents,get_embeddings_model())
        graph_documents_filter=db.similarity_search_with_relevance_scores(query,k=3)
        # print(graph_documents_filter)

        #执行CQL，得到结果
        query_result=[]
        neo4j_conn=get_neo4j_conn()
        for document in graph_documents_filter:
            question=document[0].page_content
            cypher=document[0].metadata['cypher']
            answer=document[0].metadata['answer']
            try:
                result=neo4j_conn.run(cypher).data()
                # print(question)
                # print(result)
                # exit()
                if result and any(value for value in result[0].values()):
                    # print(list(result[0].items()))
                    # exit()
                    answer_str=replace_token_in_string(answer,list(result[0].items()))
                    query_result.append(f'问题：{question}\n答案：{answer_str}')
            except:
                pass
        # print(query_result)
        # exit()
if __name__=='__main__':
    agent=Agent()
    # print(agent.generic_func('你叫什么名字？'))
    # print(agent.retrival_func('介绍一下寻医问药网'))
    # print(agent.retrival_func('寻医问药网的客服电话是多少？'))

    # print(agent.graph_func('感冒一般是什么引起的？'))
    # print(agent.graph_func('感冒吃什么药好得快？可以吃阿莫西林吗？'))

    print(agent.graph_func('感冒和鼻炎是并发症吗？'))
