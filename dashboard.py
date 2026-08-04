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
        
        # Validación segura para eventos recientes
        ultimos_eventos = []
        if hasattr(prestamo_repo, "listar_ultimos_eventos"):
            ultimos_eventos = prestamo_repo.listar_ultimos_eventos(limite=8)
        else:
            from app.models.evento import EventoFinanciero
            ultimos_eventos = db.query(EventoFinanciero).order_by(EventoFinanciero.creado_en.desc()).limit(8).all()

        total_clientes = len(clientes)
        clientes_activos = len(
            [c for c in clientes if hasattr(c, "estado") and (c.estado.value == "ACTIVO" if hasattr(c.estado, "value") else c.estado == "ACTIVO")]
        )
        clientes_bloqueados = len(
            [c for c in clientes if hasattr(c, "estado") and (c.estado.value == "BLOQUEADO" if hasattr(c.estado, "value") else c.estado == "BLOQUEADO")]
        )

        st.divider()

        # ==========================
        # MÉTRICAS FINANCIERAS
        # ==========================

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "💵 Capital Disponible",
                f"${resumen.get('caja_disponible', 0.0):,.2f}"
            )

        with col2:
            st.metric(
                "📈 Capital Prestado",
                f"${resumen.get('capital_prestado', 0.0):,.2f}"
            )

        with col3:
            st.metric(
                "🏦 Capital Total",
                f"${resumen.get('capital_total', 0.0):,.2f}"
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
                fecha_creacion = getattr(evento, "creado_en", None)
                fecha = fecha_creacion.strftime("%d/%m/%Y %H:%M") if fecha_creacion else "N/A"

                monto_val = getattr(evento, "monto", 0.0)
                monto = f"${monto_val:,.2f}" if monto_val else "-"

                tipo_evento = getattr(evento, "tipo_evento", "MOVIMIENTO")
                tipo_evento_str = tipo_evento.value if hasattr(tipo_evento, "value") else str(tipo_evento)

                with st.container():
                    col_ev1, col_ev2 = st.columns([4, 1])

                    with col_ev1:
                        st.markdown(f"**{tipo_evento_str}**")
                        st.caption(fecha)

                        observacion = getattr(evento, "observacion", "")
                        if observacion:
                            st.write(observacion)
                            st.caption(f"Usuario: {getattr(evento, 'usuario', 'admin')}")

                    with col_ev2:
                        st.markdown(f"### {monto}")

                    st.divider()

    finally:
        db.close()
