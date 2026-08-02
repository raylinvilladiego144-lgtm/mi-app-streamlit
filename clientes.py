"""
app/pages/clientes.py

Pantalla de gestión de clientes: Registro, Buscador y Lista en formato tarjetas.
"""

import streamlit as st

from app.database.database import SessionLocal
from app.models.cliente import (
    Cliente,
    CalificacionCliente,
    EstadoCliente,
)
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository


def render_clientes():
    st.title("👤 Gestión de Clientes")
    st.caption("Registro, consulta y seguimiento de la base de clientes")

    db = SessionLocal()

    try:
        cliente_repo = ClienteRepository(db)
        prestamo_repo = PrestamoRepository(db)

        tab1, tab2 = st.tabs(["📋 Lista de Clientes", "➕ Registrar Cliente"])

        # TAB 1: LISTADO Y BÚSQUEDA
        with tab1:
            busqueda = st.text_input(
                "🔍 Buscar por nombre o documento",
                placeholder="Ingrese nombre o número de cédula/documento..."
            )

            if busqueda.strip():
                clientes = cliente_repo.buscar_clientes(busqueda)
            else:
                clientes = cliente_repo.listar_todos()

            if not clientes:
                st.info("No se encontraron clientes registrados.")
            else:
                # Renderizado en tarjetas (grid de 2 columnas)
                for i in range(0, len(clientes), 2):
                    cols = st.columns(2)
                    for idx, col in enumerate(cols):
                        if i + idx < len(clientes):
                            c = clientes[i + idx]
                            with col:
                                with st.container(border=True):
                                    st.subheader(c.nombre_completo)
                                    st.write(f"**Documento:** {c.documento}")
                                    st.write(f"**Teléfono:** {c.telefono}")
                                    if c.direccion:
                                        st.write(f"**Dirección:** {c.direccion}")

                                    # Badges / Etiquetas de Estado y Calificación
                                    col_est, col_cal = st.columns(2)
                                    with col_est:
                                        st.caption(f"Estado: **{c.estado.value}**")
                                    with col_cal:
                                        st.caption(f"Calificación: **{c.calificacion.value}**")

                                    if c.observaciones:
                                        st.caption(f"*Obs:* {c.observaciones}")

        # TAB 2: REGISTRO DE NUEVO CLIENTE
        with tab2:
            st.subheader("Registrar Nuevo Cliente")

            with st.form("form_nuevo_cliente", clear_on_submit=True):
                col_a, col_b = st.columns(2)

                with col_a:
                    documento = st.text_input("Documento / Cédula *")
                    nombre = st.text_input("Nombre Completo *")
                    telefono = st.text_input("Teléfono / WhatsApp *")

                with col_b:
                    direccion = st.text_input("Dirección")
                    calificacion = st.selectbox(
                        "Calificación Inicial",
                        options=[c.value for c in CalificacionCliente],
                        index=1  # BUENO por defecto
                    )
                    observaciones = st.text_area("Observaciones", height=68)

                guardar = st.form_submit_button("Guardar Cliente", use_container_width=True)

                if guardar:
                    if not documento.strip() or not nombre.strip() or not telefono.strip():
                        st.error("Por favor complete los campos obligatorios (*).")
                    else:
                        try:
                            # Verificar disponibilidad del documento
                            existente = cliente_repo.obtener_por_documento(documento.strip())
                            if existente:
                                st.error("Ya existe un cliente registrado con este número de documento.")
                            else:
                                nuevo_cliente = Cliente(
                                    documento=documento.strip(),
                                    nombre_completo=nombre.strip(),
                                    telefono=telefono.strip(),
                                    direccion=direccion.strip() if direccion else None,
                                    calificacion=CalificacionCliente(calificacion),
                                    estado=EstadoCliente.ACTIVO,
                                    observaciones=observaciones.strip() if observaciones else None
                                )
                                cliente_repo.crear(nuevo_cliente)
                                st.success(f"Cliente '{nombre}' registrado exitosamente.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar el cliente: {e}")

    finally:
        db.close()