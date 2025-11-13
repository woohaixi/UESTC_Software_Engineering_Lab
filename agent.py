from utils import *
from config import *
from prompt import *

import os
from langchain.chains import LLMChain,LLMRequestsChain
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
# from langchain.agents import ZeroShotAgent  #ZeroShotAgent已经弃用
from langchain.agents import AgentExecutor,Tool,create_react_agent
from langchain.memory import ConversationBufferMemory
from langchain.output_parsers import ResponseSchema,StructuredOutputParser
from langchain import hub

import requests


class Agent():
    def __init__(self):
        self.vdb=Chroma(
            persist_directory=os.path.join(os.path.dirname(__file__),'./data/db'),
            embedding_function=get_embeddings_model()
        )

    def generic_func(self,x,query):
        print(x)
        print(query)
        prompt=PromptTemplate.from_template(GENERIC_PROMPT_TPL)
        llm_chain=LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        return llm_chain.invoke(query)['text']

    #填充提示词并总结答案
    def retrival_func(self,x,query):
        print(x)
        print(query)
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
        return retrival_chain.invoke(inputs)['text']

    #命名实体识别
    def graph_func(self,x,query):#这里加上x只是为了tools中的lambda匿名函数能够用上，只起到占位的作用，其他的用不上
        print(x)
        print(query)
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
        result=ner_chain.invoke({
                'query':query
            })['text']
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
        return graph_chain.invoke(inputs)['text']

    def search_func(self, query):
        # === 1. 动态启用代理（仅在此函数）===
        original_http = os.environ.get('HTTP_PROXY')
        original_https = os.environ.get('HTTPS_PROXY')

        os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
        os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
        print("代理已启用：127.0.0.1:7890")

        try:
            # === 2. 原有搜索逻辑 ===
            api_key = os.getenv('SERPER_API_KEY')
            if not api_key or api_key == '您的实际Serper_API_KEY':
                return "请设置有效的 SERPER_API_KEY 环境变量"

            print(f"使用的 Serper API Key: {api_key[:10]}...")

            url = "https://google.serper.dev/search"
            payload = {"q": query, "gl": "cn", "hl": "zh-cn"}
            headers = {
                'X-API-KEY': api_key,
                'Content-Type': 'application/json'
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code != 200:
                return f"搜索失败: {response.status_code}"

            data = response.json()
            organic = data.get('organic', [])[:3]
            if not organic:
                return "未找到相关搜索结果"

            search_results = ""
            for i, item in enumerate(organic):
                search_results += f"结果 {i + 1}:\n"
                search_results += f"标题: {item.get('title', 'N/A')}\n"
                search_results += f"摘要: {item.get('snippet', 'N/A')}\n"
                search_results += f"链接: {item.get('link', 'N/A')}\n"
                search_results += "---\n"

            prompt = PromptTemplate.from_template(SEARCH_PROMPT_TPL)
            chain = LLMChain(llm=get_llm_model(), prompt=prompt, verbose=os.getenv('VERBOSE'))
            result = chain.invoke({'query': query, 'query_result': search_results})['text']

            return result

        except Exception as e:
            return f"搜索出错: {str(e)}"

        finally:
            # === 3. 恢复原始代理设置（关键！）===
            if original_http is not None:
                os.environ['HTTP_PROXY'] = original_http
            else:
                os.environ.pop('HTTP_PROXY', None)

            if original_https is not None:
                os.environ['HTTPS_PROXY'] = original_https
            else:
                os.environ.pop('HTTPS_PROXY', None)

            print("代理已恢复")

    def _is_greeting(self, query):
        """判断是否为打招呼类问题"""
        greeting_keywords = ['你好', '您好', 'hello', 'hi', '你是谁', '你是什么', '你能做什么', 
                            '你能干什么', '介绍', '介绍一下', '你是谁开发的', '你是什么机器人']
        query_lower = query.lower().strip()
        # 检查是否包含打招呼关键词
        for keyword in greeting_keywords:
            if keyword in query_lower:
                return True
        # 检查是否是很短的问候语（通常打招呼都很简短）
        if len(query.strip()) <= 10 and not any(char in query for char in ['病', '症', '药', '治', '医', '痛', '烧', '咳']):
            return True
        return False

    def query(self,query):
        # 对于打招呼类问题，直接使用generic_func，不经过Agent
        if self._is_greeting(query):
            return self.generic_func('', query)
        
        tools=[
            Tool.from_function(
                name='generic_func',
                func=lambda x:self.generic_func(x,query),
                description='【重要】只用于回答打招呼、问你是谁、你能做什么这类基础问题。如果用户问的是医疗相关问题（疾病、症状、药物、治疗等），绝对不要使用此工具！',
            ),
            Tool.from_function(
                name='retrival_func',
                func=lambda x:self.retrival_func(x,query),
                description='用于回答关于寻医问药网网站本身的问题，比如网站介绍、联系方式、投资信息等。不用于回答医疗咨询问题。',
            ),
            Tool.from_function(
                name='graph_func',
                func=lambda x:self.graph_func(x,query),
                description='用于回答医疗相关问题，包括：疾病定义、症状、病因、治疗方法、药物、并发症、预防等。这是回答医疗咨询的主要工具。',
            ),
            Tool.from_function(
                name='search_func',
                func=self.search_func,
                description='【最后选择】当且仅当其他工具都无法回答时，才使用此工具通过搜索引擎回答通用类问题。不要轻易调用！',
            )
        ]
        # prefix = """请用中文，尽你所能回答以下问题。您可以使用以下工具：
        #         【重要规则】
        #         1. 如果是打招呼、问身份、问能力的问题，必须使用generic_func
        #         2. 如果是医疗相关问题（疾病、症状、药物、治疗等），必须使用graph_func
        #         3. 如果是关于寻医问药网网站的问题，使用retrival_func
        #         4. 只有当以上工具都无法回答时，才考虑使用search_func
        #         5. 每个问题只调用一次最合适的工具，不要重复调用多个工具"""
        # suffix = """Begin!
        #
        # History: {chat_history}
        # Question: {input}
        # Thought:{agent_scratchpad}"""
        #
        # agent_prompt = ZeroShotAgent.create_prompt(
        #     tools=tools,
        #     prefix=prefix,
        #     suffix=suffix,
        #     input_variables=['input', 'agent_scratchpad', 'chat_history'])
        # llm_chain = LLMChain(llm=get_llm_model(), prompt=agent_prompt)
        # agent = ZeroShotAgent(llm_chain=llm_chain)
        # memory = ConversationBufferMemory(memory_key='chat_history')
        # agent_chain = AgentExecutor.from_agent_and_tools(
        #     agent=agent,
        #     tools=tools,
        #     memory=memory,
        #     verbose=os.getenv('VERBOSE'),
        #     handle_parsing_errors=True,
        #     max_iterations=3,  # 限制最大迭代次数，避免重复调用
        #     max_execution_time=30)  # 限制最大执行时间
        # return agent_chain.run({'input': query})

        # prompt=PromptTemplate.from_template(REACT_CHAT_PROMPT_TPL)#网络不稳定的时候用这个本地的
        prompt = hub.pull('hwchase17/react-chat')#从langsmith社区拉取得到的提示词，不用再从头写了
        # print(prompt)
        # exit()
        prompt.template = '请用中文回答问题! Final Answer 必须尊重 Observation 的结果，不能改变语义。\\n\n' + prompt.template

        agent = create_react_agent(llm=get_llm_model(), tools=tools, prompt=prompt)
        memory = ConversationBufferMemory(memory_key='chat_history')

        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            memory=memory,
            handle_parsing_errors=True,
            verbose=os.getenv('VERBOSE')
        )

        return agent_executor.invoke({"input": query})['output']

    def parse_tools(self, tools, query):
        prompt = PromptTemplate.from_template(PARSE_TOOLS_PROMPT_TPL)
        llm_chain = LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )

        # 拼接工具描述参数
        tools_description = ''
        for tool in tools:
            tools_description += tool.name + ':' + tool.description + '\n'
        result = llm_chain.invoke({'tools_description': tools_description, 'query': query})

        # 解析工具函数
        for tool in tools:
            if tool.name == result['text']:
                return tool
        return tools[0]

if __name__=='__main__':
    agent=Agent()
    # print(agent.query('你好'))
    print(agent.query('寻医问药网获得过哪些投资？'))
    # print(agent.query('告诉我鼻炎和感冒是并发症吗？'))
    # print(agent.query('鼻炎怎么治疗？'))
    # print(agent.query('烧橙子可以治疗感冒吗？'))
    # print(agent.query('你好，你叫什么名字？'))
    # print(agent.query('你好，你可以做什么？'))
    # print(agent.query('你好，如何杀死那个石家庄人？'))  #测试暴力内容是否屏蔽
    # exit()

    # print(agent.generic_func('','你叫什么名字？'))
    # print(agent.retrival_func('','介绍一下寻医问药网'))
    # print(agent.retrival_func('','寻医问药网的客服电话是多少？'))
    # print(agent.retrival_func('', '寻医问药网获得过哪些投资？'))

    # print(agent.graph_func('','感冒一般是什么引起的？'))
    # print(agent.graph_func('','感冒吃什么药好得快？可以吃阿莫西林吗？'))
    #
    # print(agent.graph_func('','感冒和鼻炎是并发症吗？'))
    # print(agent.search_func('万能青年旅店是什么乐队？发布了几张专辑？代表歌曲有哪些？'))

