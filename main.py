"""
main.py
Punto de entrada principal con Login, base de datos limpia y gestión de préstamos.
"""

from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- IMPORTACIÓN DE MÓDULOS PLANOS ---
from prestamos import render_prestamos

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Gestión de Préstamos",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CREDENCIALES DE ACCESO ---
USUARIOS = {
    "simon": "12345",
    "raylin": "Barcelona12*",
}

DB_NAME = "prestamos_v2.db"


# --- INICIALIZACIÓN DE LA BASE DE DATOS ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS prestamos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT,
                cliente TEXT,
                monto REAL,
                interes REAL,
                cuotas INTEGER,
                fecha TEXT,
                estado TEXT
            )
        """
        )
        conn.commit()


init_db()


# --- MÓDULOS DE LA APLICACIÓN ---
def render_caja(usuario):
    st.title(f"📦 Módulo de Caja - {usuario.capitalize()}")
    st.write("Resumen financiero global de la cartera registrada.")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, cliente, monto, interes, cuotas, fecha, estado FROM prestamos WHERE usuario = ?",
            (usuario,),
        )
        rows = cursor.fetchall()

    if not rows:
        st.info("No hay transacciones registradas todavía.")
    else:
        df = pd.DataFrame(
            rows,
            columns=[
                "ID",
                "Cliente",
                "Monto",
                "Interés",
                "Cuotas",
                "Fecha",
                "Estado",
            ],
        )
        total_colocado = df["Monto"].sum()
        st.metric("Capital Total Colocado", f"${total_colocado:,.2f}")
        st.dataframe(df, use_container_width=True)


def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.write("Control de abonos y amortización de cuotas.")
    st.info("Módulo listo para registrar abonos a capital o intereses.")


def render_clientes(usuario):
    st.title(f"👥 Módulo de Clientes - {usuario.capitalize()}")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT cliente FROM prestamos WHERE usuario = ?",
            (usuario,),
        )
        rows = cursor.fetchall()

    if not rows:
        st.info("No hay clientes registrados en los préstamos.")
    else:
        df = pd.DataFrame(rows, columns=["Cliente"])
        st.dataframe(df, use_container_width=True)


# --- LOGIN ---
def login():
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
    if not st.session_state.get("logged_in", False):
        login()
        return

    usuario_actual = st.session_state.get("username", "admin")

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

    if modulo == "Caja":
        render_caja(usuario_actual)
    elif modulo == "Pagos":
        render_pagos(usuario_actual)
    elif modulo == "Préstamos":
        render_prestamos()
    elif modulo == "Clientes":
        render_clientes(usuario_actual)


if __name__ == "__main__":
    main()
