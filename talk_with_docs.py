import chromadb
import tiktoken
from google import genai
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

def summarize_emails(timedelta_int: int, count_tokens: bool = False) -> str:
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
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    question = f"Summarize documents: \n {'\n'.join(docs)} "

    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[question]
    )

    if count_tokens:
        tokenizer = tiktoken.get_encoding("cl100k_base")

        tokens = tokenizer.encode(question)
        print(f"Token count: {len(tokens)}")
    return response.text

def simple_rag(query: str, count_tokens: bool = False) -> str:
    prompt = """
    Question: {query}
    Retrieved documents: {documents}
    """
    chroma_client = chromadb.PersistentClient(path="./chromadb")
    collection = chroma_client.get_or_create_collection(name="emails")

    results = collection.query(
        query_texts=[query],
        n_results=2
    )
    prompt = prompt.format(query=query, documents="\n".join(results["documents"][0]))

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt]
    )

    if count_tokens:
        tokenizer = tiktoken.get_encoding("cl100k_base")

        tokens = tokenizer.encode(prompt)
        print(f"Token count: {len(tokens)}")

    return response.text
if __name__ == "__main__":
    load_dotenv()
    query = "What is the kernel trick?"
    #print(summarize_emails(5, count_tokens=True))
    print(simple_rag(query, count_tokens=True))

