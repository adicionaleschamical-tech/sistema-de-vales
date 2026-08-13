def mostrar_historial_detallado():
    """Muestra el historial detallado por dependencia como planilla para separar vales"""
    st.header("📜 Historial de Distribución - Planilla de Separación")
    
    try:
        detalle = obtener_detalle_entregas()
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")
        return
    
    if not detalle:
        st.info("No hay registros de entregas detalladas")
        return
    
    df_detalle = pd.DataFrame(detalle)
    
    if df_detalle.empty:
        st.info("No hay registros de entregas detalladas")
        return
    
    # Asegurar que las columnas numéricas sean float/int
    columnas_numericas = ["cuota_objetivo", "total_entregado"] + [f"vale_{d}" for d in DENOMINACIONES]
    for col in columnas_numericas:
        if col in df_detalle.columns:
            df_detalle[col] = pd.to_numeric(df_detalle[col], errors='coerce').fillna(0)
    
    # Convertir fecha
    if "fecha" in df_detalle.columns:
        try:
            df_detalle["fecha"] = pd.to_datetime(df_detalle["fecha"])
        except:
            pass
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        if not df_detalle.empty and "fecha" in df_detalle.columns:
            fechas_disponibles = sorted(df_detalle["fecha"].unique(), reverse=True)
            fecha_seleccionada = st.selectbox(
                "📅 Seleccionar fecha de distribución",
                options=["Todas"] + [str(f.date()) for f in fechas_disponibles]
            )
    with col2:
        # Opción para mostrar en formato planilla
        mostrar_planilla = st.checkbox("📋 Mostrar como planilla de separación", value=True)
    
    # Aplicar filtros
    df_filtrado = df_detalle.copy()
    if fecha_seleccionada and fecha_seleccionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["fecha"].astype(str).str.contains(fecha_seleccionada)]
    
    if df_filtrado.empty:
        st.info("No hay registros con los filtros seleccionados")
        return
    
    # Si hay múltiples registros para la misma fecha, agrupar por dependencia
    if fecha_seleccionada != "Todas":
        # Agrupar por dependencia para una misma fecha
        df_agrupado = df_filtrado.groupby(["dependencia_nombre", "dependencia_id"]).agg({
            "cuota_objetivo": "first",
            "total_entregado": "sum",
            **{f"vale_{d}": "sum" for d in DENOMINACIONES}
        }).reset_index()
        
        df_agrupado["tipo"] = df_filtrado["tipo"].iloc[0] if "tipo" in df_filtrado.columns else "AUTO"
        df_agrupado["fecha"] = df_filtrado["fecha"].iloc[0] if "fecha" in df_filtrado.columns else pd.NaT
    else:
        df_agrupado = df_filtrado
    
    if mostrar_planilla:
        # Mostrar como planilla de separación
        st.markdown("---")
        
        # Calcular total general
        total_general = df_agrupado["total_entregado"].sum() if "total_entregado" in df_agrupado.columns else 0
        
        st.markdown(f"""
        <div class="planilla-separacion">
            <h3>📋 PLANILLA DE SEPARACIÓN DE VALES</h3>
            <p><strong>Fecha:</strong> {fecha_seleccionada if fecha_seleccionada != "Todas" else "Todas las fechas"}</p>
            <p><strong>Total a distribuir:</strong> ${total_general:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar cada dependencia con sus vales
        for idx, row in df_agrupado.iterrows():
            cuota = row['cuota_objetivo'] if 'cuota_objetivo' in row else 0
            total_entregado = row['total_entregado'] if 'total_entregado' in row else 0
            
            st.markdown(f"""
            <div class="planilla-separacion">
                <div class="dependencia-item">
                    <strong>{row['dependencia_nombre']}</strong>
                    <br>
                    Cuota: ${cuota:,.0f} | Entregado: ${total_entregado:,.0f}
                    <br>
                    <strong>Vales a entregar:</strong>
                </div>
            """, unsafe_allow_html=True)
            
            # Mostrar vales en columnas
            cols = st.columns(len(DENOMINACIONES))
            
            # CORREGIDO: Calcular el total en vales correctamente
            total_vales = 0
            
            for i, denom in enumerate(DENOMINACIONES):
                col_name = f"vale_{denom}"
                cantidad = int(row[col_name]) if col_name in row and pd.notnull(row[col_name]) else 0
                total_vales += cantidad * denom
                
                with cols[i]:
                    if cantidad > 0:
                        st.metric(
                            f"${denom:,.0f}",
                            f"{cantidad}",
                            delta=f"${cantidad * denom:,.0f}"
                        )
                    else:
                        st.metric(
                            f"${denom:,.0f}",
                            "0",
                            delta=None
                        )
            
            # Mostrar total de la dependencia (CORREGIDO)
            st.markdown(f"""
                <div style="text-align: right; font-weight: bold; margin-top: 10px; 
                           padding-top: 10px; border-top: 2px solid #dee2e6;">
                    <strong>Total en vales: ${total_vales:,.0f}</strong>
                </div>
                <div style="text-align: right; color: {'#28a745' if total_vales == total_entregado else '#dc3545'};">
                    {'✅ Coincide con entregado' if total_vales == total_entregado else f'⚠️ Diferencia: ${total_entregado - total_vales:,.0f}'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Botón para descargar planilla
        if st.button("📥 Descargar planilla completa (CSV)"):
            try:
                # Crear CSV con el formato de planilla
                df_planilla = df_agrupado.copy()
                # Renombrar columnas para mejor lectura
                columnas_renombrar = {
                    "dependencia_nombre": "Dependencia",
                    "cuota_objetivo": "Cuota",
                    "total_entregado": "Total_Entregado"
                }
                for d in DENOMINACIONES:
                    columnas_renombrar[f"vale_{d}"] = f"Vale_{d}"
                df_planilla = df_planilla.rename(columns=columnas_renombrar)
                
                csv = df_planilla.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                b64 = base64.b64encode(csv).decode()
                fecha_str = fecha_seleccionada.replace("/", "-") if fecha_seleccionada != "Todas" else "todas"
                href = f'<a href="data:file/csv;base64,{b64}" download="planilla_separacion_{fecha_str}.csv">⬇️ Descargar CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error al descargar: {e}")
    
    else:
        # Mostrar como tabla normal
        st.subheader("📊 Detalle de Distribución")
        
        columnas_mostrar = ["fecha", "dependencia_nombre", "cuota_objetivo", "total_entregado", "tipo"]
        for denom in DENOMINACIONES:
            col_name = f"vale_{denom}"
            if col_name in df_agrupado.columns:
                columnas_mostrar.append(col_name)
        
        columnas_existentes = [col for col in columnas_mostrar if col in df_agrupado.columns]
        df_mostrar = df_agrupado[columnas_existentes].copy()
        
        for col in df_mostrar.columns:
            if col not in ["fecha", "dependencia_nombre", "tipo"]:
                try:
                    df_mostrar[col] = df_mostrar[col].apply(lambda x: f"${float(x):,.0f}" if pd.notnull(x) and x != 0 else "$0")
                except:
                    df_mostrar[col] = df_mostrar[col].apply(lambda x: "$0")
        
        st.dataframe(df_mostrar, use_container_width=True, height=400)
