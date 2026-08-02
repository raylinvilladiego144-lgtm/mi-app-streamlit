"""
app/pages/login.py

Pantalla de inicio de sesión minimalista.
"""

import streamlit as st

from app.security.auth import login


def render_login():
    """
    Renderiza el formulario de inicio de sesión.
    """

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        st.title("💳 Sistema de Gestión de Préstamos")
        st.caption("Ingresa tus credenciales para continuar")

        with st.form("form_login"):

            usuario = st.text_input(
                "Usuario",
                placeholder="admin"
            )

            contrasena = st.text_input(
                "Contraseña",
                type="password",
                placeholder="••••••••"
            )

            ingresar = st.form_submit_button(
                "Ingresar",
                use_container_width=True
            )

            if ingresar:

                if not usuario.strip() or not contrasena.strip():

                    st.warning(
                        "Debe ingresar usuario y contraseña."
                    )

                elif login(
                    usuario,
                    contrasena
                ):

                    st.success(
                        "Bienvenido al sistema."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Usuario o contraseña incorrectos."
                    )
                    