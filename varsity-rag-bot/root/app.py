import os
from pathlib import Path

import streamlit as st  # pyright: ignore[reportMissingImports]
from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
from groq import APIConnectionError, APIStatusError, RateLimitError

from rag_core import load_rag_chain

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

DOCUMENTS_DIR = PROJECT_DIR / "university_docs"
SUPPORTED_DOCUMENTS = {".pdf", ".md", ".txt"}


def has_documents(directory: Path) -> bool:
    return directory.is_dir() and any(
        path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENTS
        for path in directory.rglob("*")
    )


if not has_documents(DOCUMENTS_DIR):
    existing_documents_dir = PROJECT_DIR.parent / "venv" / "university_docs"
    if has_documents(existing_documents_dir):
        DOCUMENTS_DIR = existing_documents_dir

SCRAPED_DOCUMENTS_DIR = PROJECT_DIR.parent / "data" / "raw" / "scraped"
DOCUMENT_DIRECTORIES = [
    directory
    for directory in (DOCUMENTS_DIR, SCRAPED_DOCUMENTS_DIR)
    if has_documents(directory)
]
DOCUMENT_FILES = sorted(
    path
    for directory in DOCUMENT_DIRECTORIES
    for path in directory.rglob("*")
    if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENTS
)

TRANSLATIONS = {
    "বাংলা": {
        "new_chat": "নতুন কথোপকথন",
        "topics": "যে বিষয়ে জানতে পারবেন",
        "admission": "ভর্তি ও যোগ্যতা",
        "curriculum": "CSE কারিকুলাম",
        "faculty": "শিক্ষক ও কর্মকর্তারা",
        "notices": "বিভাগীয় নোটিশ",
        "documents": "নথির সংগ্রহ",
        "files_count": "ইনডেক্সে থাকা ফাইল",
        "view_documents": "নথিগুলো দেখুন",
        "no_documents": "এখনো কোনো নথি পাওয়া যায়নি।",
        "grounded": "উত্তরগুলো ইনডেক্স করা নথির ভিত্তিতে তৈরি হয়।",
        "title": "আপনার বিশ্ববিদ্যালয় সহকারী",
        "subtitle": "Eastern University সম্পর্কে প্রশ্ন করুন—বাংলা বা ইংরেজি, যেভাবেই স্বচ্ছন্দ।",
        "badge": "নথিভিত্তিক উত্তর",
        "choose_question": "কী জানতে চান?",
        "choose_hint": "একটি প্রশ্ন বেছে নিন, অথবা নিচে নিজের প্রশ্ন লিখুন।",
        "suggestions": (
            "CSE ভর্তির যোগ্যতা কী?",
            "ভর্তির জন্য কী কী কাগজ লাগবে?",
            "CSE বিভাগের কর্মকর্তারা কারা?",
            "বিশ্ববিদ্যালয়ে কোন কোন প্রোগ্রাম আছে?",
        ),
        "chat_placeholder": "আপনার প্রশ্নটি লিখুন...",
        "sources": "যে নথি থেকে উত্তর খোঁজা হয়েছে",
        "searching": "নথিতে খুঁজছি...",
        "missing_key": "Groq API key পাওয়া যায়নি। `.env` ফাইলে `GROQ_API_KEY` যোগ করুন।",
        "missing_index": "এখনো কোনো নথি ইনডেক্স করা হয়নি। Project folder থেকে `python .\\root\\ingest.py` চালান।",
        "api_busy": "Groq সাময়িকভাবে ব্যস্ত (503)। একটু পরে আবার চেষ্টা করুন।",
        "rate_limit": "Groq-এর request limit পূর্ণ হয়েছে (429)। কিছুক্ষণ অপেক্ষা করে আবার চেষ্টা করুন।",
        "api_error": "Groq service HTTP {code} দিয়েছে। API key এবং chat model যাচাই করুন।",
        "api_failure": "Groq অনুরোধটি সম্পন্ন করতে পারেনি। API key এবং chat model যাচাই করে আবার চেষ্টা করুন।",
    },
    "English": {
        "new_chat": "New conversation",
        "topics": "What you can ask",
        "admission": "Admissions and eligibility",
        "curriculum": "CSE curriculum",
        "faculty": "Faculty and officials",
        "notices": "Department notices",
        "documents": "Document library",
        "files_count": "Files in the index",
        "view_documents": "View documents",
        "no_documents": "No documents found yet.",
        "grounded": "Answers are based on the indexed documents.",
        "title": "Your university assistant",
        "subtitle": "Ask about Eastern University in English or Bangla.",
        "badge": "Document-grounded answers",
        "choose_question": "What would you like to know?",
        "choose_hint": "Choose a suggested question or type your own below.",
        "suggestions": (
            "What are the CSE admission requirements?",
            "Which documents are needed for admission?",
            "Who are the CSE faculty and officials?",
            "Which programs does the university offer?",
        ),
        "chat_placeholder": "Type your question...",
        "sources": "Sources used for this answer",
        "searching": "Searching the documents...",
        "missing_key": "Groq API key not found. Add `GROQ_API_KEY` to the project's `.env` file.",
        "missing_index": "No documents have been indexed yet. Run `python .\\root\\ingest.py` from the project folder.",
        "api_busy": "Groq is temporarily busy (503). Please try again shortly.",
        "rate_limit": "Groq's request limit was reached (429). Please wait and try again.",
        "api_error": "Groq returned HTTP {code}. Check the API key and chat model.",
        "api_failure": "Groq could not complete the request. Check the API key and chat model, then try again.",
    },
}

st.set_page_config(
    page_title="Eastern University AI",
    page_icon=":material/school:",
    layout="centered",
)


def submit_suggestion(question: str) -> None:
    st.session_state["pending_question"] = question


with st.sidebar:
    st.title("Eastern AI")
    st.caption("University information, all in one place")
    selected_language = st.selectbox(
        "Language / ভাষা",
        options=("বাংলা", "English"),
        key="selected_language",
    )
    text = TRANSLATIONS[selected_language]

    if st.button(
        text["new_chat"],
        icon=":material/add_comment:",
        type="primary",
        width="stretch",
    ):
        st.session_state["messages"] = []
        st.session_state.pop("pending_question", None)
        st.rerun()

    st.subheader(text["topics"])
    st.markdown(
        f"- :material/how_to_reg: {text['admission']}\n"
        f"- :material/menu_book: {text['curriculum']}\n"
        f"- :material/groups: {text['faculty']}\n"
        f"- :material/campaign: {text['notices']}"
    )

    st.subheader(text["documents"])
    st.caption(f"{text['files_count']}: **{len(DOCUMENT_FILES)}**")
    if DOCUMENT_FILES:
        with st.expander(text["view_documents"], icon=":material/folder_open:"):
            for document_path in DOCUMENT_FILES:
                st.caption(f":material/description: {document_path.name}")
    else:
        st.warning(text["no_documents"])

    st.caption(text["grounded"])

st.title(text["title"])
st.markdown(text["subtitle"])
st.badge(
    text["badge"],
    icon=":material/verified_user:",
    color="green",
)

if not os.getenv("GROQ_API_KEY"):
    st.error(text["missing_key"])
    st.stop()

if not (PROJECT_DIR / "chroma_db_huggingface").is_dir():
    st.error(text["missing_index"])
    st.stop()

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if not st.session_state["messages"]:
    st.subheader(text["choose_question"])
    st.caption(text["choose_hint"])
    first_row = st.columns(2)
    second_row = st.columns(2)
    for column, question in zip(
        (*first_row, *second_row),
        text["suggestions"],
        strict=True,
    ):
        with column:
            st.button(
                question,
                key=f"suggestion_{question}",
                icon=":material/arrow_outward:",
                width="stretch",
                on_click=submit_suggestion,
                args=(question,),
            )

for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander(text["sources"]):
                for source in message["sources"]:
                    st.caption(f":material/description: {source}")

user_input = st.chat_input(text["chat_placeholder"])
if not user_input:
    user_input = st.session_state.pop("pending_question", None)

if user_input:
    st.session_state["messages"].append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar=":material/school:"):
        with st.spinner(text["searching"]):
            try:
                response = load_rag_chain(selected_language).invoke(
                    {"input": user_input}
                )
            except RateLimitError:
                st.warning(text["rate_limit"])
            except APIStatusError as exc:
                if exc.status_code == 503:
                    st.warning(text["api_busy"])
                else:
                    st.error(
                        text["api_error"].format(code=exc.status_code)
                    )
            except APIConnectionError:
                st.error(text["api_failure"])
            else:
                answer = response["answer"]
                sources = sorted(
                    {
                        Path(document.metadata["source"]).name
                        for document in response.get("context", [])
                        if document.metadata.get("source")
                    }
                )
                st.markdown(answer)
                if sources:
                    with st.expander(text["sources"]):
                        for source in sources:
                            st.caption(f":material/description: {source}")
                st.session_state["messages"].append(
                    {
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    }
                )
