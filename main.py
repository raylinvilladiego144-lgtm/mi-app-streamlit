"""
main.py
Punto de entrada principal con Login y separación de datos por usuario.
"""

import streamlit as st

# Funciones de respaldo integradas para que cargue de inmediato
def render_caja(usuario):
    st.title(f"📦 Módulo de Caja - {usuario.capitalize()}")
    st.write("Aquí puedes gestionar el flujo de caja y los movimientos.")

def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.write("Aquí puedes registrar y consultar los pagos.")

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

    # 2. Obtener el usuario activo
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
        st.info(f"Módulo de Préstamos activo para {usuario_actual.capitalize()}")
    elif modulo == "Clientes":
        st.info(f"Módulo de Clientes activo para {usuario_actual.capitalize()}")


if __name__ == "__main__":
    try:
        import sqlite3
        conn = sqlite3.connect("loan_management.db")
        conn.close()
    except Exception:
        pass
    
    main()
