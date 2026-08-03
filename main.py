# --- MÓDULO 5: GESTIÓN DE RESPALDOS Y SEGURIDAD ---
def render_gestion_respaldos(usuario):
    st.markdown("## 🛡️ Gestión y Seguridad de Datos")
    st.caption("Respalda tu información o reinicia el sistema por completo si lo necesitas.")

    db_path = "prestamos_v2.db"

    col1, col2 = st.columns(2)

    # --- 1. BOTÓN DE RESPALDO (BACKUP) GLOBAL ---
    with col1:
        st.subheader("💾 Copia de Seguridad")
        st.write("Descarga una copia actual de la base de datos general.")
        
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

    # --- 2. ZONA DE PELIGRO: LIMPIEZA TOTAL DE LA BASE DE DATOS ---
    with col2:
        st.subheader("🔥 Zona de Peligro")
        st.write("Reinicia y deja la base de datos completamente en ceros.")

        with st.expander("⚠️ Desplegar opción de limpieza general", expanded=False):
            confirmar_total = st.checkbox("Confirmo que deseo borrar ABSOLUTAMENTE TODO el contenido")
            
            if st.button("💥 Borrar Todo y Dejar en Ceros", type="primary", use_container_width=True):
                if confirmar_total:
                    try:
                        if os.path.exists(db_path):
                            os.remove(db_path)
                            st.success("¡Base de datos limpiada con éxito! Recargando...")
                            st.rerun()
                        else:
                            st.warning("No se encontró el archivo de la base de datos.")
                    except Exception as e:
                        st.error(f"❌ Error al reiniciar: {e}")
                else:
                    st.warning("⚠️ Debes marcar la casilla de confirmación.")
