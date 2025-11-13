import os

from prompt import *
from utils import  *
from agent import *

from langchain.chains import LLMChain
from langchain.prompts import  Prompt

class Service():
    def __init__(self):
        self.agent=Agent()

    def get_summary_message(self,message,history):
        llm=get_llm_model()
        prompt=Prompt.from_template(SUMMARY_PROMPT_TPL)
        llm_chain=LLMChain(llm=llm,prompt=prompt,verbose=os.getenv('VERBOSE'))
        chat_history=''
        for item in history[-2:]:#取最近两轮的对话内容
            # 处理history格式不一致的情况
            if len(item) >= 2:
                # 标准格式：[问题, 答案]
                q, a = item[0], item[1]
                chat_history+=f'问题：{q},答案：{a}\n'
            elif len(item) == 1:
                # 只有一个元素，可能是只有问题或只有答案，作为问题处理
                chat_history+=f'问题：{item[0]}\n'
        return llm_chain.run(query=message,chat_history=chat_history)

    def answer(self,message,history):
        if history:
            message=self.get_summary_message(message,history)
        print(message)
        return self.agent.query(message)


if __name__=='__main__':
    service=Service()
    # print(service.answer('你好',[]))
    # print(service.answer('得了鼻炎怎么办？',[['你好','你好，有什么可以帮到你吗？']]))
    # print(service.answer('是感冒的并发症吗? ', [
    #     ['你好，有什么可以帮到您的吗? '],
    #     ['得了鼻炎怎么办？', '可以考虑使用丙酸氟替卡松鼻喷雾剂、头孢克洛颗粒等药物进行治疗。'],
    # ]))
    print(service.answer('大概多长时间能治好? ', [
        ['你好，有什么可以帮到您的吗? '],
        ['得了鼻炎怎么办？', '可以考虑使用丙酸氟替卡松鼻喷雾剂、头孢克洛颗粒等药物进行治疗。'],
    ]))