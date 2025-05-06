import streamlit as st
from talk_with_docs import summarize_emails, simple_rag
from gmail_fetch import authenticate_gmail, get_emails, update_chromadb
from dotenv import load_dotenv
import os

st.set_page_config(
    page_title="Talk with LLM"
)

st.title("Talk with LLM")
generation_config = {}
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

with st.sidebar:
    generation_config["temperature"] = st.slider(
        label="Temperature",
        min_value=0.0,
        max_value=2.0,
        value=0.1,
    )

    generation_config["max_output_tokens"] = st.slider(
        label="Max output tokens",
        min_value=0,
        max_value=10000,
        value=2000,
    )

    span_of_days = st.slider(
        label="Span of days (to summarize or update DB)",
        min_value=0,
        max_value=31,
        value=7,
    )

    n_results = st.slider(
        label="Number of documents for RAG",
        min_value=0,
        max_value=10,
        value=2,
    )

    count_tokens = st.checkbox("Count input tokens")

    options = st.multiselect(
        "Choose action:",
        ["Summarize", "Answer your query", "Update DB"],
        max_selections=1,
        accept_new_options=False,
    )
    left, middle, right = st.columns([0.3, 0.6, 0.1])
    if options:
        if options[0] == "Answer your query":
            query = st.text_input(
                label="Write your query:"
            )
        elif options[0] == "Summarize":
            with middle:
                summarize_flag = st.button("Summarize", type="primary")
        elif options[0] == "Update DB":
            with middle:
                update_db_flag = st.button("Update DB", type="primary")
        
if options:
    if options[0] == "Answer your query":
        if query:
            st.write("Query: ", query)
            response, num_tokens = simple_rag(query, generation_config=generation_config, api_key=GEMINI_API_KEY, count_tokens=count_tokens, n_results=n_results)
            if num_tokens:
                st.write(f"**Number of input tokens**: {num_tokens}")
            st.markdown(response)
    elif options[0] == "Summarize":
        if summarize_flag:
            st.write("Summarized emails:")
            response, num_tokens = summarize_emails(span_of_days, generation_config, api_key=GEMINI_API_KEY, count_tokens=count_tokens)
            if num_tokens:
                st.write(f"**Number of input tokens**: {num_tokens}")
            st.markdown(response)
    elif options[0] == "Update DB":
        if update_db_flag:
            st.write("Updating DB...")
            service = authenticate_gmail()
            emails = os.getenv("EMAIL_LIST").split(",")

            emails = get_emails(service, emails, max_results=100, timedelta_days=span_of_days)
            message = update_chromadb(emails)
            st.write(message)
