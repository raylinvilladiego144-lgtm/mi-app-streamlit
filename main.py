"""
main.py
Punto de entrada principal con Login y separación de datos por usuario.
"""

import streamlit as st

from app.pages.caja import render_caja
from app.pages.pagos import render_pagos
# Si tienes vistas para Clientes o Préstamos, impórtalas aquí:
# from app.pages.clientes import render_clientes
# from app.pages.prestamos import render_prestamos

# Credenciales de acceso para la aplicación
USUARIOS = {
    "simon": "12345",
    "raylin": "12345",
}

st.set_page_config(
    page_title="Gestión de Préstamos",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)


def login():
    """Pantalla y formulario de inicio de sesión."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Iniciar Sesión")
        st.caption("Sistema de Gestión de Préstamos e Inversiones")

        with st.form("form_login"):
            usr = st.text_input("Usuario").strip().lower()
            pwd = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button(
                "Ingresar", type="primary", use_container_width=True
            )

            if btn:
                if usr in USUARIOS and USUARIOS[usr] == pwd:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = usr
                    st.success(f"¡Bienvenido, {usr.capitalize()}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")


def main():
    # 1. Verificar si el usuario ha iniciado sesión
    if not st.session_state.get("logged_in", False):
        login()
        return

    # 2. Obtener el usuario activo ("simon" o "raylin")
    usuario_actual = st.session_state.get("username", "admin")

    # 3. Menú Lateral (Sidebar)
    with st.sidebar:
        st.title("💳 Sistema Préstamos")
        st.markdown(f"👤 **Usuario activo:** `{usuario_actual.capitalize()}`")
        st.divider()

        modulo = st.selectbox(
            "Seleccionar Módulo",
            ["Caja", "Pagos", "Préstamos", "Clientes"],
        )

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # 4. Enrutamiento de páginas pasando el usuario en sesión
    if modulo == "Caja":
        render_caja(usuario_actual)
    elif modulo == "Pagos":
        render_pagos(usuario_actual)
    elif modulo == "Préstamos":
        # render_prestamos(usuario_actual)
        st.info(f"Módulo de Préstamos activo para {usuario_actual.capitalize()}")
    elif modulo == "Clientes":
        # render_clientes(usuario_actual)
        st.info(f"Módulo de Clientes activo para {usuario_actual.capitalize()}")


if __name__ == "__main__":
    # Inicializar las tablas en Supabase automáticamente al arrancar la app
    from app.database.database import init_db
    init_db()
    
    main()