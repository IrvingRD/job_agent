import streamlit as st

from guardrails import input_guardrail, output_guardrail
from llm_client import call_llm
from prompts import DEFAULT_PROMPTS


st.set_page_config(
    page_title="JobGPT",
    page_icon="💼",
    layout="centered",
)


APP_TITLE = "💼 JobGPT"
APP_DESCRIPTION = (
    "Agente conversacional para búsqueda laboral, CV, entrevistas "
    "y posicionamiento profesional."
)


def initialize_session_state():
    if "selected_profile" not in st.session_state:
        st.session_state.selected_profile = list(DEFAULT_PROMPTS.keys())[0]

    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = DEFAULT_PROMPTS[
            st.session_state.selected_profile
        ]

    if "messages" not in st.session_state:
        reset_conversation()


def reset_conversation():
    st.session_state.messages = [
        {
            "role": "system",
            "content": st.session_state.system_prompt,
        },
        {
            "role": "assistant",
            "content": (
                "Hola, soy JobGPT. Puedo ayudarte a mejorar tu búsqueda laboral. "
                "Para empezar, cuéntame brevemente: ¿qué tipo de puesto buscas, "
                "en qué país o ciudad, y cuál es tu experiencia principal?"
            ),
        },
    ]


def apply_new_prompt():
    """
    Actualiza el system prompt en el historial.
    Mantiene la conversación visible, pero cambia la instrucción principal.
    """

    if "messages" in st.session_state and st.session_state.messages:
        if st.session_state.messages[0]["role"] == "system":
            st.session_state.messages[0]["content"] = st.session_state.system_prompt
        else:
            st.session_state.messages.insert(
                0,
                {
                    "role": "system",
                    "content": st.session_state.system_prompt,
                },
            )


def trim_messages(messages, max_messages=16):
    """
    Reduce el historial enviado al LLM para controlar costos.
    Conserva siempre el system prompt y los mensajes más recientes.
    """

    if not messages:
        return []

    system_message = messages[0]

    non_system_messages = [
        message for message in messages[1:] if message["role"] != "system"
    ]

    recent_messages = non_system_messages[-max_messages:]

    return [system_message] + recent_messages


initialize_session_state()


# =========================
# Sidebar
# =========================

with st.sidebar:
    st.header("Configuración del agente")

    selected_profile = st.selectbox(
        "Perfil objetivo",
        options=list(DEFAULT_PROMPTS.keys()),
        index=list(DEFAULT_PROMPTS.keys()).index(st.session_state.selected_profile),
    )

    if selected_profile != st.session_state.selected_profile:
        st.session_state.selected_profile = selected_profile
        st.session_state.system_prompt = DEFAULT_PROMPTS[selected_profile]
        reset_conversation()
        st.rerun()

    st.markdown("---")

    st.subheader("Prompt del sistema")

    edited_prompt = st.text_area(
        "Puedes editar el objetivo y comportamiento del agente",
        value=st.session_state.system_prompt,
        height=350,
    )

    if edited_prompt != st.session_state.system_prompt:
        st.session_state.system_prompt = edited_prompt
        apply_new_prompt()

    st.markdown("---")

    model = st.selectbox(
        "Modelo",
        options=[
            "gpt-4o-mini",
            "gpt-4o",
        ],
        index=0,
    )

    temperature = st.slider(
        "Temperatura",
        min_value=0.0,
        max_value=1.0,
        value=0.4,
        step=0.1,
    )

    max_tokens = st.slider(
        "Máximo de tokens de respuesta",
        min_value=300,
        max_value=2000,
        value=900,
        step=100,
    )

    st.markdown("---")

    if st.button("🧹 Borrar historial de conversación", use_container_width=True):
        reset_conversation()
        st.success("Historial borrado.")
        st.rerun()

    st.caption(
        "En esta versión, el historial se guarda solo en memoria de sesión "
        "con st.session_state. No se escribe en disco ni en GitHub."
    )


# =========================
# Main app
# =========================

st.title(APP_TITLE)
st.caption(APP_DESCRIPTION)

st.info(
    "Versión inicial: chat con historial en sesión, prompt editable y perfiles "
    "predefinidos. La carga de CVs/documentos se agregará en el siguiente paso."
)


# Mostrar historial visible, excepto mensaje system
for message in st.session_state.messages:
    if message["role"] == "system":
        continue

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


user_input = st.chat_input("Escribe tu mensaje...")

if user_input:
    allowed, guardrail_message = input_guardrail(user_input)

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    if not allowed:
        response = guardrail_message

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        with st.chat_message("assistant"):
            st.markdown(response)

    else:
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    messages_for_llm = trim_messages(st.session_state.messages)

                    response = call_llm(
                        messages=messages_for_llm,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                    response = output_guardrail(response)

                except Exception as e:
                    response = (
                        "Ocurrió un error al llamar al modelo. "
                        f"Detalle técnico: {e}"
                    )

                st.markdown(response)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )