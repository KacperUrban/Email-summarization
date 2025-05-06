import chromadb
import tiktoken
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from time import sleep
import streamlit as st

def get_response_from_llm(gemini_client: genai.Client, prompt: str, system_prompt: str, generation_config: dict, sleep_time: int = 2) -> str:
    """This function generate response to user prompt. Also if API server is overloaded, function will retry API call with
    certain sleep time (gap between API calls). In this function you can specify some configuration parameters like temperature 
    or system prompt.

    Args:
        gemini_client (genai.Client): gemini client object
        prompt (str): user prompt (question which you want to ask)
        system_prompt (str): some suggestion how model have to behaviour
        generation_config (dict): this dictionary contains config values (like temperature, max output tokens)
        sleep_time (int): number of seconds which function will be wait before next call to API. Defaults to 2 seconds.

    Returns:
        str: function returns extracted text from LLM response
    """
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                max_output_tokens=generation_config["max_output_tokens"],
                temperature=generation_config["temperature"],
                system_instruction=system_prompt,
            ),
            contents=[prompt],
        )
    except:
        print("Retrying call to LLM API...")
        sleep(sleep_time)
        get_response_from_llm(gemini_client, prompt, generation_config)
    return response.text


def summarize_emails(timedelta_int: int, generation_config: dict, api_key: str, count_tokens: bool = False) -> str:
    """This function will summarize retrieved documents from specified interval. Data are gathered from chromdb. So 
    if in database documents not appear, function will return comment to user.
    Args:
        timedelta_int (int): number of days, in which emails will be summarized
        count_tokens (bool, optional): flags to control whether count the tokens. Defaults to False.

    Returns:
        str: summarize text for retrived documents.
    """
    system_prompt = """You are an machine learning expert with 10 years experience. Your goal is to summarize indicated documents. You have to
    do your best to get essence out of this documents. Your audience mainly will be STEM student, who want to be a Data Scientist in future. You should
    propose to 5 topics to explore (you can propose less). If you propose something, you can get the link or title of the email to deepen knowledge. If you think none of this topics is important, only summarize text. Some documents will be
    in Polish, but some in English. In order to standardize generate only text in English."""
    chroma_client = chromadb.PersistentClient(path="./chromadb")
    collection = chroma_client.get_or_create_collection(name="emails")

    all_data = collection.get(include=["documents", "metadatas"])

    date_timedelta_days = datetime.now() - timedelta(days=timedelta_int)
    docs = []
    for data, metadata in zip(all_data["documents"], all_data["metadatas"]):
        date = datetime.strptime(metadata["date"], "%d:%m:%Y")
        if date >= date_timedelta_days:
            docs.append(data)
    if not docs:
        return "You have no documents to summarize! Please add some to database!"
    
    gemini_client = genai.Client(api_key=api_key)

    prompt = f"Summarize documents: \n {'\n'.join(docs)} "

    response = get_response_from_llm(gemini_client, prompt, system_prompt, generation_config)

    if count_tokens:
        tokenizer = tiktoken.get_encoding("cl100k_base")

        tokens = tokenizer.encode(prompt)
        return response, len(tokens)
    return response, None

@st.cache_data
def simple_rag(query: str, generation_config: dict, api_key: str, count_tokens: bool = False, n_results: int = 2) -> str:
    """This function will respnse to user query, based on retrieved documents from chromadb. If there is no documents model should
    inform user, that question is based on his embeded knowledge.

    Args:
        query (str): user query
        count_tokens (bool, optional): flags to control whether count the tokens. Defaults to False.
v
    Returns:
        str: response on the query based on retrieved documents.
    """
    system_prompt = """You are an machine learning expert with 10 years experience. Your goal is to precise response to question mainly
    based on provided documents. If you dont find important information in documents, highlight that you used your embeded knowledge. Your audience
    mainly will be STEM student, who want to be a Data Scientist in future. If in your opinion some topic will be diffcult break it down to smaller ones.
    Some documents will be in Polish, but some in English. In order to standardize generate only text in English.
    """
    prompt = """
    Question: {query}
    Retrieved documents: {documents}
    """
    chroma_client = chromadb.PersistentClient(path="./chromadb")
    collection = chroma_client.get_or_create_collection(name="emails")

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
    )
    prompt = prompt.format(query=query, documents="\n".join(results["documents"][0]))

    gemini_client = genai.Client(api_key=api_key)

    response = get_response_from_llm(gemini_client, prompt, system_prompt, generation_config)

    if count_tokens:
        tokenizer = tiktoken.get_encoding("cl100k_base")

        tokens = tokenizer.encode(prompt)
        return response, len(tokens)

    return response, None
if __name__ == "__main__":
    load_dotenv()
    query = "What is the kernel trick?"

    generation_config = {
        "max_output_tokens" : 1000,
        "temperature" : 0.1,
    }
    #print(summarize_emails(10, generation_config=generation_config, count_tokens=True))
    #print(simple_rag(query, generation_config=generation_config, count_tokens=True))

