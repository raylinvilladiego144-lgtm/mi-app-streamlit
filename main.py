"""
main.py
Punto de entrada principal con Login, Dashboard financiero y gestión de préstamos.
"""

from datetime import datetime
import pandas as pd
import streamlit as st

# --- IMPORTACIÓN DE MÓDULOS PLANOS ---
from database import SessionLocal, init_db
from caja_service import CajaService
from prestamos import render_prestamos

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Gestión de Préstamos e Inversiones",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- INICIALIZAR LAS TABLAS DE SQLALCHEMY AUTOMÁTICAMENTE ---
init_db()

# --- CREDENCIALES DE ACCESO ---
USUARIOS = {
    "simon": "12345",
    "raylin": "Barcelona12*",
}


# --- MÓDULOS DE LA APLICACIÓN (DASHBOARD) ---
def render_dashboard(usuario):
    st.title(f"📊 Dashboard Financiero — {usuario.capitalize()}")
    st.markdown("Resumen general del estado de caja, capital en la calle y flujos de efectivo.")

    db = SessionLocal()
    try:
        caja_service = CajaService(db, usuario_actual=usuario)
        resumen = caja_service.obtener_resumen_financiero()

        # --- MÉTRICAS PRINCIPALES ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="💵 Caja Disponible",
                value=f"${resumen['caja_disponible']:,.2f}",
                help="Dinero disponible en efectivo o banco para nuevos préstamos o retiros."
            )

        with col2:
            st.metric(
                label="📈 Capital Prestado (Activo)",
                value=f"${resumen['capital_prestado']:,.2f}",
                help="Saldo pendiente por cobrar en los préstamos activos."
            )

        with col3:
            st.metric(
                label="🏦 Capital Total (Caja + Cartera)",
                value=f"${resumen['capital_total']:,.2f}",
                help="Patrimonio total administrado."
            )

        st.divider()

        # --- SECCIÓN DE MOVIMIENTOS RECIENTES ---
        st.subheader("📜 Últimos Movimientos y Transacciones")
        movimientos = caja_service.listar_movimientos(limite=10)

        if not movimientos:
            st.info("No hay movimientos financieros registrados todavía en este usuario.")
        else:
            data = []
            for m in movimientos:
                data.append({
                    "ID": m.id,
                    "Fecha": getattr(m, "fecha", "N/A"),
                    "Tipo": m.tipo_evento.value if hasattr(m.tipo_evento, "value") else str(m.tipo_evento),
                    "Monto": f"${m.monto:,.2f}" if hasattr(m, "monto") else "$0.00",
                    "Observación": getattr(m, "observacion", "")
                })
            
            df_movs = pd.DataFrame(data)
            st.dataframe(df_movs, use_container_width=True, hide_index=True)

    finally:
        db.close()


def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.write("Control de abonos y amortización de cuotas.")
    st.info("Módulo de pagos configurado y listo para enlazar con cuotas.")


def render_clientes(usuario):
    st.title(f"👥 Módulo de Clientes - {usuario.capitalize()}")
    st.info("Gestión de directorio de clientes.")


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
            ["Dashboard / Caja", "Préstamos", "Pagos", "Clientes"],
        )

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if modulo == "Dashboard / Caja":
        render_dashboard(usuario_actual)
    elif modulo == "Préstamos":
        render_prestamos()
    elif modulo == "Pagos":
        render_pagos(usuario_actual)
    elif modulo == "Clientes":
        render_clientes(usuario_actual)


if __name__ == "__main__":
    main()
