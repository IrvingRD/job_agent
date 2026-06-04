import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def get_openai_api_key():
    """
    Obtiene la API key desde Streamlit secrets o desde .env.

    Prioridad:
    1. st.secrets["OPENAI_API_KEY"]
    2. Variable de entorno OPENAI_API_KEY
    """

    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

    return os.getenv("OPENAI_API_KEY")


def get_client():
    api_key = get_openai_api_key()

    if not api_key:
        raise ValueError(
            "No se encontró OPENAI_API_KEY. Configúrala en .env localmente "
            "o en st.secrets para Streamlit Cloud."
        )

    return OpenAI(api_key=api_key)


def call_llm(
    messages,
    model="gpt-4o-mini",
    temperature=0.4,
    max_tokens=900,
):
    client = get_client()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content