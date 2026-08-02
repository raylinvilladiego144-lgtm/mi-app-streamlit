"""
app/pages/dashboard.py

Pantalla principal de indicadores clave y lista de últimos movimientos.
"""

import streamlit as st

from app.database.database import SessionLocal
from app.services.caja_service import CajaService
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository


def render_dashboard():
    st.markdown("## 📊 Dashboard General")
    st.caption("Resumen en tiempo real del estado financiero y de cartera")

    db = SessionLocal()

    try:
        caja_service = CajaService(db)
        cliente_repo = ClienteRepository(db)
        prestamo_repo = PrestamoRepository(db)

        # Obtener información
        resumen = caja_service.obtener_resumen_financiero()
        clientes = cliente_repo.listar_todos()
        prestamos_activos = prestamo_repo.listar_activos()
        ultimos_eventos = prestamo_repo.listar_ultimos_eventos(limite=8)

        total_clientes = len(clientes)
        clientes_activos = len(
            [c for c in clientes if c.estado.value == "ACTIVO"]
        )
        clientes_bloqueados = len(
            [c for c in clientes if c.estado.value == "BLOQUEADO"]
        )

        st.divider()

        # ==========================
        # MÉTRICAS FINANCIERAS
        # ==========================

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "💵 Capital Disponible",
                f"${resumen['caja_disponible']:,.2f}"
            )

        with col2:
            st.metric(
                "📈 Capital Prestado",
                f"${resumen['capital_prestado']:,.2f}"
            )

        with col3:
            st.metric(
                "🏦 Capital Total",
                f"${resumen['capital_total']:,.2f}"
            )

        st.divider()

        # ==========================
        # MÉTRICAS OPERATIVAS
        # ==========================

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "👥 Clientes",
                total_clientes
            )

        with c2:
            st.metric(
                "✅ Activos",
                clientes_activos
            )

        with c3:
            st.metric(
                "🚫 Bloqueados",
                clientes_bloqueados
            )

        with c4:
            st.metric(
                "📄 Préstamos Activos",
                len(prestamos_activos)
            )

        st.divider()

        # ==========================
        # ÚLTIMOS MOVIMIENTOS
        # ==========================

        st.subheader("🕒 Últimos Movimientos")

        if not ultimos_eventos:
            st.info("No existen movimientos registrados.")

        else:
            for evento in ultimos_eventos:
                fecha = evento.creado_en.strftime("%d/%m/%Y %H:%M")

                monto = (
                    f"${evento.monto:,.2f}"
                    if evento.monto
                    else "-"
                )

                with st.container():
                    col1, col2 = st.columns([4, 1])

                    with col1:
                        st.markdown(f"**{evento.tipo_evento.value}**")
                        st.caption(fecha)

                        if evento.observacion:
                            st.write(evento.observacion)
                            st.caption(f"Usuario: {evento.usuario}")

                    with col2:
                        st.markdown(f"### {monto}")

                    st.divider()

    finally:
        db.close()