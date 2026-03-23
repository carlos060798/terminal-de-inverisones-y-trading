"""Table Service — TAPAS-based table question answering."""


def query_table(table_data, question):
    """Ask a natural-language question about tabular data using the TAPAS model.

    Parameters
    ----------
    table_data : dict
        Table in the format expected by the HF TAPAS endpoint
        (e.g. ``{"table": {"Column": [values]}, ...}``).
    question : str
        The question to answer.

    Returns
    -------
    str
        The answer string, or an error message.
    """
    try:
        from backends import hf_backend
        return hf_backend.table_qa(table_data, question)
    except Exception as e:
        return f"Error en consulta de tabla: {e}"
