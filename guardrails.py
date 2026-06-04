FORBIDDEN_PATTERNS = [
    "mentir en mi cv",
    "mentir en el cv",
    "inventar experiencia",
    "inventarme experiencia",
    "falsificar experiencia",
    "falsificar un título",
    "crear un título falso",
    "hacer parecer que trabajé",
    "engañar al reclutador",
    "engañar a recursos humanos",
    "fingir experiencia",
    "fingir que trabajé",
]


def input_guardrail(user_input: str):
    """
    Valida el mensaje del usuario antes de llamar al LLM.

    Returns:
        allowed: bool
        message: str | None
    """

    text = user_input.lower()

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in text:
            return False, (
                "No puedo ayudarte a mentir, falsificar experiencia, títulos "
                "o logros profesionales. Sí puedo ayudarte a presentar tu "
                "experiencia real de forma más clara, estratégica y atractiva "
                "para el puesto que buscas."
            )

    return True, None


def output_guardrail(response: str) -> str:
    """
    Guardrail básico de salida.
    En esta primera versión solo hacemos validaciones simples.
    """

    risky_phrases = [
        "te garantizo que conseguirás trabajo",
        "garantizo que conseguirás empleo",
        "inventa que",
        "di que trabajaste aunque no",
    ]

    lowered = response.lower()

    for phrase in risky_phrases:
        if phrase in lowered:
            return (
                "Voy a reformular la respuesta para mantenerla ética y profesional. "
                "No es correcto inventar experiencia ni garantizar resultados. "
                "Puedo ayudarte a mejorar tu posicionamiento usando información real."
            )

    return response