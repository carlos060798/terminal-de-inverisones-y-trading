"""
file_saver.py — Export inteligente para desktop y navegador.
En modo desktop (pywebview): guarda en ~/Documents/QuantumExports/
En modo browser: usa st.download_button normal.
"""
import os
import streamlit as st
from pathlib import Path
from datetime import datetime


def _is_desktop() -> bool:
    """Detecta si la app corre dentro de pywebview (desktop mode)."""
    return os.environ.get("QUANTUM_DESKTOP", "") == "1"


def _export_folder() -> Path:
    """Carpeta de exportación en Documents."""
    folder = Path.home() / "Documents" / "QuantumExports"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_or_download(data: bytes, filename: str, mime: str, label: str, key: str = None):
    """
    Exportar archivo: guarda en disco (desktop) o descarga (browser).

    Args:
        data: bytes del archivo (Excel, PDF, etc.)
        filename: nombre del archivo (ej: 'cartera_quantum.xlsx')
        mime: tipo MIME (ej: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        label: texto del botón (ej: '📥 Exportar Cartera')
        key: key único para st.download_button (evitar duplicados)
    """
    if _is_desktop():
        # Modo desktop → guardar en Documents/QuantumExports/
        folder = _export_folder()
        # Agregar timestamp para no sobreescribir
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_name = f"{stem}_{ts}{suffix}"
        path = folder / final_name
        try:
            path.write_bytes(data)
            st.success(f"✅ Guardado en: `{path}`")
            st.caption(f"📂 Abrir carpeta: `{folder}`")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")
    else:
        # Modo browser → download button normal
        st.download_button(
            label=label,
            data=data,
            file_name=filename,
            mime=mime,
            key=key,
        )


def open_export_folder():
    """Abrir la carpeta de exports en el explorador de Windows."""
    folder = _export_folder()
    if os.name == "nt":
        os.startfile(str(folder))
    st.info(f"📂 Carpeta: `{folder}`")
