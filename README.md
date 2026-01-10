<h1>基于Langchain和知识图谱的医疗问答系统</h1>
参考了相关网课，加了一点前端实现
实验所需环境可以通过requirements.txt进行一键安装:  
pip install -r requirements.txt
实验需要创建一个.env文件，把下面的复制粘贴到.env中即可，APIKeys填你所购买的秘钥：  
OPENAI_API_BASE=YOUR_OPENAI_API_BASE  
OPENAI_API_KEY=YOUR_OPENAI_API_KEY  
SERPER_API_KEY=YOUR_SERPER_API_KEY  

EMBEDDINGS_MODEL='openai'  
OPENAI_EMBEDDINGS_MODEL='text-embedding-ada-002'  

LLM_MODEL='openai'  
OPENAI_LLM_MODEL='gpt-4.1-mini'  

TEMPERATURE=0  
MAX_TOKENS=1000  

VERBOSE=True  

NEO4J_URI='bolt://localhost:7687'   #注意！py2neo这里只能用bolt:而不是neo4j:  
NEO4J_USERNAME='neo4j'  
NEO4J_PASSWORD=YOUR_NEO4J_PASSWORD  

LANGSMITH_TRACING=True  
LANGSMITH_ENDPOINT='https://api.smith.langchain.com'  
LANGSMITH_API_KEY=YOUR_LANGSMITH_API_KEY  
LANGSMITH_PROJECT='pr-indelible-sow-36'  
