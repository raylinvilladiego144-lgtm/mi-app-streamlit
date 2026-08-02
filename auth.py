"""
app/security/auth.py

Módulo de autenticación del Sistema de Gestión de Préstamos.
Lee las credenciales desde el archivo .env utilizando python-dotenv.
"""

import os

from dotenv import load_dotenv
import streamlit as st

# ==========================================================
# CARGAR VARIABLES DE ENTORNO
# ==========================================================

load_dotenv()

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")


# ==========================================================
# SESIÓN
# ==========================================================

def inicializar_sesion() -> None:
    """
    Inicializa las variables de sesión de Streamlit.
    """

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if "usuario" not in st.session_state:
        st.session_state["usuario"] = None


# ==========================================================
# VALIDACIÓN DE CREDENCIALES
# ==========================================================

def verificar_credenciales(
    usuario: str,
    contrasena: str
) -> bool:
    """
    Verifica si las credenciales coinciden con las configuradas
    en el archivo .env.
    """

    return (
        usuario.strip() == ADMIN_USER
        and contrasena.strip() == ADMIN_PASSWORD
    )


# ==========================================================
# LOGIN
# ==========================================================

def login(
    usuario: str,
    contrasena: str
) -> bool:
    """
    Intenta iniciar sesión.

    Retorna True si las credenciales son válidas.
    """

    if verificar_credenciales(
        usuario,
        contrasena
    ):

        st.session_state["autenticado"] = True
        st.session_state["usuario"] = usuario

        return True

    return False


# ==========================================================
# LOGOUT
# ==========================================================

def logout() -> None:
    """
    Finaliza la sesión del usuario.
    """

    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None

    st.rerun()