import streamlit as st

from file_utils import SUPPORTED_FILE_TYPES, process_uploaded_files
from guardrails import input_guardrail, output_guardrail
from llm_client import call_llm
from prompts import DEFAULT_PROMPTS


st.set_page_config(
    page_title="Peludito GPT",
    page_icon="💼",
    layout="centered",
)


APP_TITLE = "💼 Peludito GPT"
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

    if "uploaded_documents_context" not in st.session_state:
        st.session_state.uploaded_documents_context = ""

    if "uploaded_image_parts" not in st.session_state:
        st.session_state.uploaded_image_parts = []

    if "uploaded_files_summary" not in st.session_state:
        st.session_state.uploaded_files_summary = []

    if "uploaded_files_errors" not in st.session_state:
        st.session_state.uploaded_files_errors = []

    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

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
                "Hola, soy Peludito GPT. Puedo ayudarte a mejorar tu búsqueda laboral. "
                "Para empezar, cuéntame brevemente: ¿qué tipo de puesto buscas, "
                "en qué país o ciudad, y cuál es tu experiencia principal?"
            ),
        },
    ]


def clear_all_data():
    """
    Borra conversación y archivos procesados en memoria.
    No borra archivos en disco porque la app no guarda archivos en disco.
    """

    st.session_state.uploaded_documents_context = ""
    st.session_state.uploaded_image_parts = []
    st.session_state.uploaded_files_summary = []
    st.session_state.uploaded_files_errors = []
    st.session_state.uploader_key += 1

    reset_conversation()


def apply_new_prompt():
    """
    Actualiza el system prompt en el historial.
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


def inject_uploaded_context(messages):
    """
    Inserta el contexto de archivos cargados en la llamada al LLM.

    - Texto extraído de documentos: se agrega como mensaje system.
    - Imágenes: se adjuntan al último mensaje del usuario como contenido multimodal.
    """

    prepared_messages = [message.copy() for message in messages]

    documents_context = st.session_state.uploaded_documents_context
    image_parts = st.session_state.uploaded_image_parts

    if documents_context:
        context_message = {
            "role": "system",
            "content": (
                "El usuario ha cargado uno o más archivos. "
                "A continuación tienes texto extraído de esos archivos. "
                "Úsalo como contexto para responder, especialmente si el usuario "
                "pregunta por su CV, experiencia, documentos, datos o tablas. "
                "No inventes información que no esté en el contexto.\n\n"
                f"{documents_context}"
            ),
        }

        prepared_messages.insert(1, context_message)

    if image_parts:
        for i in range(len(prepared_messages) - 1, -1, -1):
            if prepared_messages[i]["role"] == "user":
                original_content = prepared_messages[i]["content"]

                if isinstance(original_content, str):
                    text_content = original_content
                else:
                    text_content = str(original_content)

                prepared_messages[i]["content"] = [
                    {
                        "type": "text",
                        "text": (
                            f"{text_content}\n\n"
                            "El usuario también cargó una o más imágenes. "
                            "Analízalas solo si son relevantes para la consulta. "
                            "Si son CVs escaneados, capturas o documentos visuales, "
                            "extrae la información útil de manera cuidadosa."
                        ),
                    },
                    *image_parts,
                ]

                break

    return prepared_messages


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
        clear_all_data()
        st.rerun()

    st.markdown("---")

    st.subheader("Prompt del sistema")

    edited_prompt = st.text_area(
        "Puedes editar el objetivo y comportamiento del agente",
        value=st.session_state.system_prompt,
        height=300,
    )

    if edited_prompt != st.session_state.system_prompt:
        st.session_state.system_prompt = edited_prompt
        apply_new_prompt()

    st.markdown("---")

    model = st.selectbox(
        "Modelo",
        options=[
            "gpt-4o-mini",
            "gpt-4o"
        ],
        index=0,
        help="Para imágenes usa un modelo multimodal como gpt-4o-mini o gpt-4o.",
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
        max_value=2500,
        value=1000,
        step=100,
    )

    st.markdown("---")

    st.subheader("Archivos")

    uploaded_files = st.file_uploader(
        "Carga CVs, documentos, tablas o imágenes",
        type=SUPPORTED_FILE_TYPES,
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}",
        help=(
            "Formatos soportados: PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, JPEG, WEBP. "
            "Los archivos se procesan en memoria y no se guardan en disco."
        ),
    )

    if st.button("📎 Procesar archivos cargados", use_container_width=True):
        if not uploaded_files:
            st.warning("Primero carga uno o más archivos.")
        else:
            with st.spinner("Procesando archivos en memoria..."):
                result = process_uploaded_files(uploaded_files)

                st.session_state.uploaded_documents_context = result[
                    "documents_context"
                ]
                st.session_state.uploaded_image_parts = result["image_parts"]
                st.session_state.uploaded_files_summary = result["files_summary"]
                st.session_state.uploaded_files_errors = result["errors"]

            st.success("Archivos procesados correctamente.")

    if st.session_state.uploaded_files_summary:
        st.markdown("**Archivos procesados:**")

        for item in st.session_state.uploaded_files_summary:
            st.caption(
                f"- {item['filename']} | {item['type']} | {item['status']}"
            )

    if st.session_state.uploaded_files_errors:
        st.markdown("**Errores:**")

        for error in st.session_state.uploaded_files_errors:
            st.error(f"{error['filename']}: {error['error']}")

    st.markdown("---")

    if st.button(
        "🧹 Borrar historial y archivos cargados",
        use_container_width=True,
    ):
        clear_all_data()
        st.success("Historial y archivos cargados borrados de la sesión.")
        st.rerun()

    st.caption(
        "En esta versión, el historial y los archivos se mantienen solo en memoria "
        "de sesión con st.session_state. No se escriben en disco ni en GitHub."
    )


# =========================
# Main app
# =========================

st.title(APP_TITLE)
st.caption(APP_DESCRIPTION)

st.info(
    "Puedes cargar CVs, PDFs, Word, CSV, Excel o imágenes desde la barra lateral. "
    "Luego pregúntale al agente algo como: 'Analiza mi CV' o "
    "'Adapta mi perfil a esta vacante'."
)


if st.session_state.uploaded_files_summary:
    with st.expander("Ver archivos cargados en esta sesión"):
        for item in st.session_state.uploaded_files_summary:
            st.write(f"**{item['filename']}** — {item['status']}")

        if st.session_state.uploaded_documents_context:
            st.caption(
                "Hay texto extraído de documentos disponible como contexto para el agente."
            )

        if st.session_state.uploaded_image_parts:
            st.caption(
                f"Hay {len(st.session_state.uploaded_image_parts)} imagen(es) "
                "disponible(s) como contexto multimodal."
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
                    messages_for_llm = inject_uploaded_context(messages_for_llm)

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