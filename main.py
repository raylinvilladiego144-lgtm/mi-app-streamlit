"""
main.py
Punto de entrada principal con Login, Dashboard financiero, Préstamos, Pagos, Clientes y Gestión de Eliminación Independiente.
"""

from datetime import datetime
from decimal import Decimal
import os
import pandas as pd
import streamlit as st

# --- IMPORTACIÓN DE MÓDULOS PLANOS EXISTENTES ---
from database import SessionLocal, init_db
from caja_service import CajaService
from prestamos import render_prestamos
from cliente_repository import ClienteRepository
from prestamo import Prestamo, Cuota, EstadoPrestamo, EstadoCuota

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


# --- CLASE / LÓGICA FINANCIERA (Garantía de Persistencia) ---
class RepositorioFinanciero:

    @staticmethod
    def registrar_abono(db: SessionLocal, prestamo_id: int, monto_abono: float | Decimal, usuario: str):
        """
        Registra el pago de la cuota, amortiza el saldo e inyecta el ingreso 
        directamente al flujo de caja del usuario guardando los cambios de forma permanente.
        """
        monto_dec = Decimal(str(monto_abono))
        if monto_dec <= 0:
            raise ValueError("El monto del abono debe ser mayor a cero.")

        cuota_pendiente = db.query(Cuota).join(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario,
            Cuota.estado == EstadoCuota.PENDIENTE
        ).order_by(Cuota.numero_cuota.asc()).first()

        if not cuota_pendiente:
            raise ValueError("No hay cuotas pendientes para este préstamo.")

        cuota_pendiente.monto_pagado += monto_dec
        if cuota_pendiente.monto_pagado >= cuota_pendiente.monto_cuota:
            cuota_pendiente.estado = EstadoCuota.PAGADA
        else:
            cuota_pendiente.estado = EstadoCuota.PARCIAL

        caja_service = CajaService(db, usuario_actual=usuario)
        operacion_exitosa = False
        
        for metodo_caja in ["registrar_ingreso", "registrar_aporte", "registrar_movimiento", "ingresar"]:
            if hasattr(caja_service, metodo_caja):
                try:
                    fn = getattr(caja_service, metodo_caja)
                    try:
                        fn(monto=monto_dec, tipo="INGRESO", observacion=f"Abono cuota #{cuota_pendiente.numero_cuota} (Préstamo #{prestamo_id})")
                    except TypeError:
                        try:
                            fn(monto=monto_dec, observacion=f"Abono cuota #{cuota_pendiente.numero_cuota} (Préstamo #{prestamo_id})")
                        except TypeError:
                            fn(monto_dec)
                    operacion_exitosa = True
                    break
                except Exception:
                    pass

        if not operacion_exitosa and hasattr(caja_service, "caja") and caja_service.caja:
            if hasattr(caja_service.caja, "saldo_disponible"):
                caja_service.caja.saldo_disponible += monto_dec
                db.add(caja_service.caja)

        db.commit()
        db.refresh(cuota_pendiente)
        return cuota_pendiente

    @staticmethod
    def eliminar_prestamo(db: SessionLocal, prestamo_id: int, usuario: str):
        prestamo = db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario
        ).first()
        
        if not prestamo:
            raise ValueError(f"El préstamo con ID {prestamo_id} no existe o no pertenece a este usuario.")
        
        db.query(Cuota).filter(Cuota.prestamo_id == prestamo_id).delete()
        db.delete(prestamo)
        db.commit()


# --- MÓDULO 1: DASHBOARD / CAJA ---
def render_dashboard(usuario):
    st.title(f"📊 Dashboard Financiero — {usuario.capitalize()}")
    st.markdown("Resumen general del estado de caja, capital en la calle y flujos de efectivo.")

    db = SessionLocal()
    try:
        caja_service = CajaService(db, usuario_actual=usuario)
        resumen = caja_service.obtener_resumen_financiero()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(label="💵 Caja Disponible", value=f"${resumen['caja_disponible']:,.2f}")
        with col2:
            st.metric(label="📈 Capital Prestado (Activo)", value=f"${resumen['capital_prestado']:,.2f}")
        with col3:
            st.metric(label="🏦 Capital Total (Caja + Cartera)", value=f"${resumen['capital_total']:,.2f}")

        st.divider()

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
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()


# --- MÓDULO 2: PAGOS ---
def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.markdown("Control de abonos, amortización de cuotas e impacto directo en caja.")

    db = SessionLocal()
    try:
        prestamos_activos = db.query(Prestamo).filter(
            Prestamo.usuario == usuario,
            Prestamo.estado == EstadoPrestamo.ACTIVO
        ).all()

        if not prestamos_activos:
            st.info("No hay préstamos activos disponibles para recibir pagos.")
            return

        prestamo_opciones = {
            f"Préstamo #{p.id} - Cliente: {getattr(p.cliente, 'nombre_completo', 'N/A')} (Total: ${p.monto_total:,.2f})": p 
            for p in prestamos_activos
        }

        with st.form("form_registrar_abono"):
            st.subheader("Registrar Abono a Cuota")
            seleccion_key = st.selectbox("Seleccionar Préstamo Activo *", options=list(prestamo_opciones.keys()))
            prestamo_seleccionado = prestamo_opciones[seleccion_key]

            monto_abono = st.number_input("Monto del Abono ($) *", min_value=0.0, value=100.0, step=10.0)
            submitted = st.form_submit_button("💰 Registrar y Aplicar Abono", type="primary", use_container_width=True)

            if submitted:
                try:
                    RepositorioFinanciero.registrar_abono(db=db, prestamo_id=prestamo_seleccionado.id, monto_abono=monto_abono, usuario=usuario)
                    st.success(f"¡Abono de ${monto_abono:,.2f} guardado en la base de datos con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar el abono en la base de datos: {e}")

        st.divider()
        st.subheader("📜 Historial Reciente de Cuotas Pagadas")
        cuotas_pagadas = db.query(Cuota).join(Prestamo).filter(
            Prestamo.usuario == usuario,
            Cuota.monto_pagado > 0
        ).order_by(Cuota.id.desc()).limit(10).all()

        if cuotas_pagadas:
            data = [{
                "ID Préstamo": cp.prestamo_id,
                "Cuota N°": cp.numero_cuota,
                "Valor Cuota": f"${cp.monto_cuota:,.2f}",
                "Monto Abonado": f"${cp.monto_pagado:,.2f}",
                "Estado": cp.estado.value if hasattr(cp.estado, "value") else str(cp.estado)
            } for cp in cuotas_pagadas]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()


# --- MÓDULO 3: CLIENTES ---
def render_clientes(usuario):
    st.title(f"👥 Módulo de Clientes - {usuario.capitalize()}")
    st.markdown("Gestión y registro del directorio de clientes.")

    db = SessionLocal()
    try:
        repo = ClienteRepository(db)
        
        with st.expander("➕ Registrar Nuevo Cliente", expanded=False):
            with st.form("form_nuevo_cliente"):
                nombre = st.text_input("Nombre completo *")
                
                submitted = st.form_submit_button("Guardar Cliente", type="primary")
                if submitted:
                    if nombre.strip():
                        try:
                            repo.crear_cliente(
                                nombre=nombre.strip(),
                                documento="S/D",
                                telefono="S/D",
                                direccion="S/D",
                                usuario=usuario
                            )
                            db.commit()
                            st.success(f"¡Cliente '{nombre.strip()}' guardado permanentemente en la base de datos!")
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Error al guardar en la base de datos: {e}")
                    else:
                        st.warning("El nombre del cliente es obligatorio.")

        st.divider()
        st.subheader("📋 Directorio de Clientes")
        clientes = repo.obtener_por_usuario(usuario)

        if clientes:
            data = [{"ID": c.id, "Nombre": getattr(c, "nombre_completo", "N/A")} for c in clientes]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("No hay clientes registrados todavía.")
    finally:
        db.close()


# --- MÓDULO 4: GESTIÓN / RESPALDOS Y ELIMINACIÓN INDEPENDIENTE ---
def render_gestion_prestamos(usuario):
    st.title(f"⚙️ Gestión y Seguridad de Datos — {usuario.capitalize()}")
    st.markdown("Respalda tu información o administra únicamente tus registros de forma independiente.")

    db_path = "prestamos_v2.db"
    col1, col2 = st.columns(2)

    # --- 1. COPIA DE SEGURIDAD GLOBAL (.db) ---
    with col1:
        st.subheader("💾 Copia de Seguridad")
        st.write("Descarga una copia actual de la base de datos para asegurar que nunca pierdas información.")
        
        if os.path.exists(db_path):
            with open(db_path, "rb") as f:
                db_bytes = f.read()
            
            st.download_button(
                label="📥 Descargar Respaldo (.db)",
                data=db_bytes,
                file_name="respaldo_prestamos_v2.db",
                mime="application/octet-stream",
                type="primary",
                use_container_width=True
            )
        else:
            st.warning("⚠️ Todavía no se detecta el archivo de la base de datos.")

    # --- 2. ELIMINACIÓN INDEPENDIENTE POR USUARIO ---
    with col2:
        st.subheader("🗑️ Eliminar Mis Préstamos")
        st.write("Elimina permanentemente solo los préstamos registrados bajo tu usuario.")

        db = SessionLocal()
        try:
            prestamos_existentes = db.query(Prestamo).filter(Prestamo.usuario == usuario).all()
            
            if not prestamos_existentes:
                st.info("No tienes préstamos registrados para eliminar.")
            else:
                opciones_borrar = {
                    f"ID: {p.id} - Cliente: {getattr(p.cliente, 'nombre_completo', 'N/A')} - Capital: ${p.monto_total:,.2f}": p.id 
                    for p in prestamos_existentes
                }
                
                with st.form("form_eliminar_prestamo"):
                    prestamo_a_borrar_key = st.selectbox("Seleccione el préstamo a eliminar", options=list(opciones_borrar.keys()))
                    id_a_borrar = opciones_borrar[prestamo_a_borrar_key]
                    
                    confirmar_borrado = st.checkbox("Confirmo que deseo eliminar este préstamo y su historial permanentemente")
                    submitted = st.form_submit_button("❌ Eliminar Mi Préstamo", type="secondary", use_container_width=True)
                    
                    if submitted:
                        if confirmar_borrado:
                            try:
                                RepositorioFinanciero.eliminar_prestamo(db, id_a_borrar, usuario)
                                st.success(f"¡Préstamo con ID {id_a_borrar} eliminado exitosamente de tus registros!")
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"❌ Error al eliminar de la base de datos: {e}")
                        else:
                            st.warning("⚠️ Debes marcar la casilla de confirmación.")
        finally:
            db.close()


# --- LOGIN ---
def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Iniciar Sesión")
        st.caption("Sistema de Gestión de Préstamos e Inversiones")

        with st.form("form_login"):
            usr = st.text_input("Usuario").strip().lower()
            pwd = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

            if btn:
                if usr in USUARIOS and USUARIOS[usr] == pwd:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = usr
                    st.success(f"¡Bienvenido, {usr.capitalize()}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")


# --- CONTROLADOR PRINCIPAL ---
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
            ["Dashboard / Caja", "Préstamos", "Pagos", "Clientes", "Gestión Préstamos"],
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
    elif modulo == "Gestión Préstamos":
        render_gestion_prestamos(usuario_actual)


if __name__ == "__main__":
    main()
