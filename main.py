"""
main.py
Punto de entrada principal con Login, base de datos SQLite y gestión de préstamos.
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

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

# --- INICIALIZACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect("loan_management.db")
    cursor = conn.cursor()
    # Tabla de Préstamos
    cursor.execute("""
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
    """)
    conn.commit()
    conn.close()

init_db()

# --- MÓDULOS DE LA APLICACIÓN ---
def render_caja(usuario):
    st.title(f"📦 Módulo de Caja - {usuario.capitalize()}")
    st.write("Resumen financiero global de la cartera registrada.")
    
    conn = sqlite3.connect("loan_management.db")
    df = pd.read_sql_query("SELECT * FROM prestamos WHERE usuario = ?", conn, params=(usuario,))
    conn.close()
    
    if df.empty:
        st.info("No hay transacciones registradas todavía.")
    else:
        total_colocado = df["monto"].sum()
        st.metric("Capital Total Colocado", f"${total_colocado:,.2f}")
        st.dataframe(df, use_container_width=True)

def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.write("Control de abonos y amortización de cuotas.")
    # Aquí puedes listar los pagos asociados
    st.info("Módulo listo para registrar abonos a capital o intereses.")

def render_prestamos(usuario):
    st.title(f"📋 Módulo de Préstamos - {usuario.capitalize()}")
    
    with st.form("form_nuevo_prestamo", clear_on_submit=True):
        st.subheader("Registrar Nuevo Préstamo")
        col1, col2 = st.columns(2)
        with col1:
            cliente = st.text_input("Nombre del Cliente")
            monto = st.number_input("Monto del Préstamo ($)", min_value=0.0, step=100.0)
            interes = st.number_input("Tasa de Interés (%)", min_value=0.0, step=0.1)
        with col2:
            cuotas = st.number_input("Número de Cuotas", min_value=1, step=1, value=1)
            fecha = st.date_input("Fecha de Emisión", value=datetime.today())
            estado = st.selectbox("Estado", ["Activo", "Finalizado", "Atrasado"])
            
        submitted = st.form_submit_button("Guardar Préstamo en Base de Datos", type="primary")
        
        if submitted:
            if not cliente.strip():
                st.warning("El nombre del cliente es obligatorio.")
            else:
                conn = sqlite3.connect("loan_management.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO prestamos (usuario, cliente, monto, interes, cuotas, fecha, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (usuario, cliente, monto, interes, cuotas, str(fecha), estado))
                conn.commit()
                conn.close()
                st.success(f"¡Préstamo para {cliente} guardado con éxito!")
                st.rerun()

    st.divider()
    st.subheader("Tus Préstamos Registrados")
    conn = sqlite3.connect("loan_management.db")
    df = pd.read_sql_query("SELECT id, cliente, monto, interes, cuotas, fecha, estado FROM prestamos WHERE usuario = ?", conn, params=(usuario,))
    conn.close()
    
    if df.empty:
        st.info("Aún no tienes préstamos digitalizados.")
    else:
        st.dataframe(df, use_container_width=True)

def render_clientes(usuario):
    st.title(f"👥 Módulo de Clientes - {usuario.capitalize()}")
    conn = sqlite3.connect("loan_management.db")
    df = pd.read_sql_query("SELECT DISTINCT cliente FROM prestamos WHERE usuario = ?", conn, params=(usuario,))
    conn.close()
    
    if df.empty:
        st.info("No hay clientes registrados en los préstamos.")
    else:
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
        render_prestamos(usuario_actual)
    elif modulo == "Clientes":
        render_clientes(usuario_actual)

if __name__ == "__main__":
    main()
