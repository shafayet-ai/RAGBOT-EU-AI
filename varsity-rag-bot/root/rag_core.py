"""Shared Groq + Hugging Face + Chroma RAG chain for all app frontends."""

from functools import lru_cache
from pathlib import Path
import re

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

PROJECT_DIR = Path(__file__).resolve().parent
CHAT_MODEL_NAME = "qwen/qwen3.8-27b"
EMBEDDING_MODEL_NAME = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
VECTORSTORE_DIRECTORY = PROJECT_DIR / "chroma_db_huggingface"
load_dotenv(PROJECT_DIR / ".env")


@lru_cache(maxsize=1)
def _load_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=2)
def load_rag_chain(answer_language: str):
    vectorstore = Chroma(
        persist_directory=str(VECTORSTORE_DIRECTORY),
        embedding_function=_load_embeddings(),
        collection_name="university_docs",
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    def retrieve_documents(request: dict[str, str]) -> list[Document]:
        query = request["input"]
        if re.search(
            r"\b(?:faculty|officials?|staff|teachers?)\b|শিক্ষক|কর্মকর্তা|অনুষদ",
            query,
            re.IGNORECASE,
        ):
            return vectorstore.similarity_search(
                query,
                k=20,
                filter={"document_type": "faculty"},
            )
        return retriever.invoke(query)


    answer_language_instruction = (
        "Answer in Bangla."
        if answer_language == "বাংলা"
        else "Answer in English."
    )
    system_prompt = (
        "আপনি বিশ্ববিদ্যালয়ের একজন প্রাতিষ্ঠানিক সহায়তা প্রদানকারী এআই। "
        "প্রদত্ত নথির (Context) তথ্যের ভিত্তিতে ব্যবহারকারীর প্রশ্নের সঠিক উত্তর দিন। "
        "তথ্য না থাকলে সোজাসুজি বলুন যে বিষয়টি নথিতে নেই। নিজের মন থেকে কোনো তথ্য বানিয়ে বলবেন না। "
        "কেউ বা কর্মকর্তাদের তালিকা চাইলে প্রাসঙ্গিক প্রাপ্ত নথির সব নাম এবং "
        "তাদের উল্লেখিত পদ অন্তর্ভুক্ত করুন; একটি আংশিক অংশ দেখে তালিকাটি সম্পূর্ণ "
        "বলে দাবি করবেন না। Overlapping chunks can repeat entries: merge details "
        "and list each person once, using the title associated with that person "
        "elsewhere in the retrieved chunks instead of reporting it as missing. "
        f"{answer_language_instruction}\n\n"
        "নথি (Context):\n{context}"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )
    llm = ChatGroq(model=CHAT_MODEL_NAME, temperature=0)
    qa_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(RunnableLambda(retrieve_documents), qa_chain)
