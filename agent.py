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

import requests

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'#调用wikipedia/google等互联网网站搜索
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

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
    def graph_func(self,x,query):
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
        # exit()

        #执行CQL，得到结果
        query_result=[]
        neo4j_conn=get_neo4j_conn()
        for document in graph_documents_filter:#document[0]是内容，document[1]是分数
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

        prompt=PromptTemplate.from_template(GRAPH_PROMPT_TPL)
        graph_chain=LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        inputs={
            'query':query,
            'query_result':"\n\n".join(query_result) if len(query_result) else '没有查到'
        }
        return graph_chain.run(inputs)

    def search_func(self, query):
        # 先验证 API Key
        api_key = os.getenv('SERPER_API_KEY')
        if not api_key or api_key == '您的实际Serper_API_KEY':
            return "请设置有效的 SERPER_API_KEY 环境变量"

        url = "https://google.serper.dev/search"
        payload = {"q": query, "gl": "cn", "hl": "zh-cn"}
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }

        try:
            # 直接调用 Serper API
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                return f"搜索失败: {response.status_code}"

            data = response.json()

            # 提取前10条结果，格式化成你想要的结构
            search_results = ""
            organic = data.get('organic', [])
            if not organic:
                search_results = "未找到相关搜索结果"
            else:
                for i, item in enumerate(organic[:10]):
                    search_results += f"结果 {i + 1}:\n"
                    search_results += f"标题: {item.get('title', 'N/A')}\n"
                    search_results += f"摘要: {item.get('snippet', 'N/A')}\n"
                    search_results += f"链接: {item.get('link', 'N/A')}\n"
                    search_results += "---\n"

            # 使用你 prompt.py 中已定义的 SEARCH_PROMPT_TPL
            prompt = PromptTemplate.from_template(SEARCH_PROMPT_TPL)
            chain = LLMChain(llm=get_llm_model(), prompt=prompt, verbose=os.getenv('VERBOSE'))

            # 传入变量（必须和你的模板变量名一致）
            result = chain.run({
                'query': query,
                'query_result': search_results  # 确保你的模板里用的是 {query_result}
            })

            return result

        except Exception as e:
            return f"搜索出错: {str(e)}"

    def query(self,query):
        tools=[
            Tool.from_function(
                name='generic_func',
                func=self.generic_func,
                description='可以解答通用领域知识，例如打招呼，问你是谁等问题',
            ),
            Tool.from_function(
                name='retrival_func',
                func=self.retrival_func,
                description='用于回答寻医问药网相关问题',
            ),
            Tool.from_function(
                name='graph_func',
                func=lambda x:self.graph_func(x,query),
                description='用于回答疾病、症状、药物等医疗相关问题',
            ),
            Tool.from_function(
                name='search_func',
                func=self.search_func,
                description='其他工具没有正确答案时，通过搜索引擎，回答通用类问题',
            )
        ]

if __name__=='__main__':
    agent=Agent()
    # print(agent.generic_func('你叫什么名字？'))
    # print(agent.retrival_func('介绍一下寻医问药网'))
    # print(agent.retrival_func('寻医问药网的客服电话是多少？'))

    # print(agent.graph_func('感冒一般是什么引起的？'))
    # print(agent.graph_func('感冒吃什么药好得快？可以吃阿莫西林吗？'))

    # print(agent.graph_func('感冒和鼻炎是并发症吗？'))
    print(agent.search_func('万能青年旅店是什么乐队？发布了几张专辑？代表歌曲有哪些？'))