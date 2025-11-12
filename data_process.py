from utils import *

import os
from glob import glob
from langchain.vectorstores.chroma import Chroma
from langchain.document_loaders import CSVLoader,PyMuPDFLoader,TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def doc2vec():
    text_splitter=RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50
    )
    dir_path= os.path.join(os.path.dirname(__file__), 'data','inputs').replace('\\', '/')
    documents=[]
    for file_path in glob(dir_path+'/*.*'):
        loader=None
        if '.csv' in file_path.lower():
            loader = CSVLoader(file_path, encoding='utf-8')
        if '.pdf' in file_path.lower():
            loader = PyMuPDFLoader(file_path)
        if '.txt' in file_path.lower():
            loader = TextLoader(file_path, encoding='utf-8')
        if loader:
            documents+=loader.load_and_split(text_splitter)
    print(documents)

if __name__ == '__main__':
    doc2vec()