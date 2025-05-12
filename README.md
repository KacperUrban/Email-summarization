# Email-summarization
# General info
This project was for create simple app or script for preprocessing email directly from Gmail, store them and summarize or use RAG on them. For retrieving emails from Gmail I used google API. For preprocessing sake I used regex and html2text. During RAG and summarization for response I used Gemini API and gemini 2.0 flash model. As a storage I used chromadb, because it is a simple DB and generate embeddings automaticaly. I used also streamlit to easily navigate. If you are curious please watch demo.
# How to use it?
1. Fork and clone my repo
2. Create Google Cloud Project and OAUTH to generate credentials (this is a simple tutorial - [link](https://mailtrap.io/blog/send-emails-with-gmail-api/)
3. Copy credientials to project folder
4. Create virutal enviroment and install all dependencies (pip install -r req.txt)
5. Run gmail_fetch.py script to initialize DB (with the Streamlit interface during initlization I got some errors)
6. Run this command to run streamlit interface: streamlit run streamlit_app.py
# Demo
Short demo video you can find under this [link](https://youtu.be/JFdNEP_YE5w?si=e8uncdx62faC1LCX) - it is too big to upload directly in readme.
# Techonologies
* Google API
* Gemini API
* chromadb
* streamlit
* regex
* html2text
* os
# Status
Project has been completed.
