def mostrar_historial_detallado():
    """Muestra el historial detallado por dependencia - Calcula el total desde los vales"""
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
    columnas_numericas = ["cuota_objetivo", "total_entregado"]
    for d in DENOMINACIONES:
        col_name = f"vale_{d}"
        if col_name in df_detalle.columns:
            columnas_numericas.append(col_name)
    
    for col in columnas_numericas:
        if col in df_detalle.columns:
            df_detalle[col] = pd.to_numeric(df_detalle[col], errors='coerce').fillna(0)
    
    # Convertir fecha
    if "fecha" in df_detalle.columns:
        try:
            df_detalle["fecha"] = pd.to_datetime(df_detalle["fecha"])
        except:
            pass
    else:
        df_detalle["fecha"] = datetime.now()
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        if "fecha" in df_detalle.columns:
            fechas_disponibles = sorted(df_detalle["fecha"].unique(), reverse=True)
            fecha_seleccionada = st.selectbox(
                "📅 Seleccionar fecha de distribución",
                options=["Todas"] + [str(f.date()) for f in fechas_disponibles if pd.notnull(f)]
            )
        else:
            fecha_seleccionada = "Todas"
    
    with col2:
        mostrar_planilla = st.checkbox("📋 Mostrar como planilla de separación", value=True)
    
    # Aplicar filtros
    df_filtrado = df_detalle.copy()
    if fecha_seleccionada and fecha_seleccionada != "Todas" and "fecha" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["fecha"].astype(str).str.contains(fecha_seleccionada)]
    
    if df_filtrado.empty:
        st.info("No hay registros con los filtros seleccionados")
        return
    
    # CORREGIDO: Para una fecha específica, mostrar los datos tal como están
    if fecha_seleccionada != "Todas":
        df_mostrar = df_filtrado.copy()
    else:
        # Solo agrupar si las columnas existen
        columnas_agrupacion = []
        if "dependencia_nombre" in df_filtrado.columns:
            columnas_agrupacion.append("dependencia_nombre")
        if "dependencia_id" in df_filtrado.columns:
            columnas_agrupacion.append("dependencia_id")
        
        if columnas_agrupacion:
            agg_dict = {}
            if "fecha" in df_filtrado.columns:
                agg_dict["fecha"] = "first"
            if "cuota_objetivo" in df_filtrado.columns:
                agg_dict["cuota_objetivo"] = "first"
            if "tipo" in df_filtrado.columns:
                agg_dict["tipo"] = "first"
            
            for d in DENOMINACIONES:
                col_name = f"vale_{d}"
                if col_name in df_filtrado.columns:
                    agg_dict[col_name] = "sum"
            
            try:
                df_mostrar = df_filtrado.groupby(columnas_agrupacion).agg(agg_dict).reset_index()
            except Exception as e:
                st.warning(f"Error al agrupar datos: {e}")
                df_mostrar = df_filtrado
        else:
            df_mostrar = df_filtrado
    
    # CORREGIDO: Calcular el total a partir de los vales para CADA registro
    for idx, row in df_mostrar.iterrows():
        total_calculado = 0
        for denom in DENOMINACIONES:
            col_name = f"vale_{denom}"
            if col_name in row:
                cantidad = int(row[col_name]) if pd.notnull(row[col_name]) else 0
                total_calculado += cantidad * denom
        df_mostrar.at[idx, "total_vales_calculado"] = total_calculado
    
    if mostrar_planilla:
        st.markdown("---")
        
        total_general = df_mostrar["total_vales_calculado"].sum() if "total_vales_calculado" in df_mostrar.columns else 0
        total_cuotas = df_mostrar["cuota_objetivo"].sum() if "cuota_objetivo" in df_mostrar.columns else 0
        
        st.markdown(f"""
        <div class="planilla-separacion">
            <h3>📋 PLANILLA DE SEPARACIÓN DE VALES</h3>
            <p><strong>Fecha:</strong> {fecha_seleccionada if fecha_seleccionada != "Todas" else "Todas las fechas"}</p>
            <p><strong>Total cuotas:</strong> ${total_cuotas:,.0f}</p>
            <p><strong>Total entregado en vales:</strong> ${total_general:,.0f}</p>
            <p><strong>Diferencia total:</strong> ${total_cuotas - total_general:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
        
        for idx, row in df_mostrar.iterrows():
            cuota = row['cuota_objetivo'] if 'cuota_objetivo' in row else 0
            total_entregado = row['total_vales_calculado'] if 'total_vales_calculado' in row else 0
            diferencia = cuota - total_entregado
            
            nombre_dependencia = row['dependencia_nombre'] if 'dependencia_nombre' in row else "Sin nombre"
            
            # Determinar color según la diferencia
            if diferencia == 0:
                color = "#28a745"  # Verde
                estado = "✅ Cumplido"
            elif diferencia > 0:
                color = "#dc3545"  # Rojo
                estado = f"⚠️ Faltan ${diferencia:,.0f}"
            else:
                color = "#ffc107"  # Amarillo
                estado = f"⚠️ Sobran ${abs(diferencia):,.0f}"
            
            st.markdown(f"""
            <div class="planilla-separacion">
                <div class="dependencia-item" style="border-left: 4px solid {color};">
                    <strong>{nombre_dependencia}</strong>
                    <br>
                    <span style="color: #6c757d;">Cuota:</span> <strong>${cuota:,.0f}</strong> | 
                    <span style="color: #6c757d;">Entregado:</span> <strong>${total_entregado:,.0f}</strong>
                    <br>
                    <span style="color: #6c757d;">Estado:</span> <strong style="color: {color};">{estado}</strong>
                    <br>
                    <span style="color: #6c757d;">Vales a entregar:</span>
                </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(len(DENOMINACIONES))
            
            total_mostrado = 0
            for i, denom in enumerate(DENOMINACIONES):
                col_name = f"vale_{denom}"
                cantidad = int(row[col_name]) if col_name in row and pd.notnull(row[col_name]) else 0
                total_mostrado += cantidad * denom
                
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
            
            st.markdown(f"""
                <div style="text-align: right; font-weight: bold; margin-top: 10px; 
                           padding-top: 10px; border-top: 2px solid #dee2e6;">
                    <strong>Total en vales: ${total_mostrado:,.0f}</strong>
                </div>
                <div style="text-align: right; color: {color}; margin-bottom: 10px;">
                    {estado}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("📥 Descargar planilla completa (CSV)"):
            try:
                df_planilla = df_mostrar.copy()
                columnas_renombrar = {
                    "dependencia_nombre": "Dependencia",
                    "cuota_objetivo": "Cuota",
                    "total_vales_calculado": "Total_Entregado"
                }
                for d in DENOMINACIONES:
                    col_name = f"vale_{d}"
                    if col_name in df_planilla.columns:
                        columnas_renombrar[col_name] = f"Vale_{d}"
                
                columnas_existentes_renombrar = {k: v for k, v in columnas_renombrar.items() if k in df_planilla.columns}
                df_planilla = df_planilla.rename(columns=columnas_existentes_renombrar)
                
                csv = df_planilla.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                b64 = base64.b64encode(csv).decode()
                fecha_str = fecha_seleccionada.replace("/", "-") if fecha_seleccionada != "Todas" else "todas"
                href = f'<a href="data:file/csv;base64,{b64}" download="planilla_separacion_{fecha_str}.csv">⬇️ Descargar CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error al descargar: {e}")
    
    else:
        st.subheader("📊 Detalle de Distribución")
        
        columnas_mostrar = []
        if "fecha" in df_mostrar.columns:
            columnas_mostrar.append("fecha")
        if "dependencia_nombre" in df_mostrar.columns:
            columnas_mostrar.append("dependencia_nombre")
        if "cuota_objetivo" in df_mostrar.columns:
            columnas_mostrar.append("cuota_objetivo")
        if "total_vales_calculado" in df_mostrar.columns:
            columnas_mostrar.append("total_vales_calculado")
        if "tipo" in df_mostrar.columns:
            columnas_mostrar.append("tipo")
        
        for denom in DENOMINACIONES:
            col_name = f"vale_{denom}"
            if col_name in df_mostrar.columns:
                columnas_mostrar.append(col_name)
        
        columnas_existentes = [col for col in columnas_mostrar if col in df_mostrar.columns]
        df_tabla = df_mostrar[columnas_existentes].copy()
        
        for col in df_tabla.columns:
            if col not in ["fecha", "dependencia_nombre", "tipo"]:
                try:
                    df_tabla[col] = df_tabla[col].apply(lambda x: f"${float(x):,.0f}" if pd.notnull(x) and x != 0 else "$0")
                except:
                    df_tabla[col] = df_tabla[col].apply(lambda x: "$0")
        
        st.dataframe(df_tabla, use_container_width=True, height=400)
