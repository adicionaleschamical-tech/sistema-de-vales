def mostrar_historial_detallado():
    """Muestra el historial detallado por dependencia - SOLO MUESTRA DATOS GUARDADOS"""
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
        # Si no existe fecha, crear columna dummy
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
    
    # NO RE-CALCULAR NADA - Mostrar los datos tal como están guardados
    # Si hay múltiples registros para la misma fecha, agruparlos por dependencia
    if fecha_seleccionada != "Todas":
        # Para una fecha específica, agrupar por dependencia (puede haber varios registros si hubo múltiples distribuciones)
        columnas_agrupacion = []
        if "dependencia_nombre" in df_filtrado.columns:
            columnas_agrupacion.append("dependencia_nombre")
        if "dependencia_id" in df_filtrado.columns:
            columnas_agrupacion.append("dependencia_id")
        
        if columnas_agrupacion:
            # Crear diccionario de agregación
            agg_dict = {}
            if "fecha" in df_filtrado.columns:
                agg_dict["fecha"] = "first"
            if "cuota_objetivo" in df_filtrado.columns:
                agg_dict["cuota_objetivo"] = "first"
            if "total_entregado" in df_filtrado.columns:
                agg_dict["total_entregado"] = "sum"  # Sumar si hay múltiples registros
            if "tipo" in df_filtrado.columns:
                agg_dict["tipo"] = "first"
            
            # Agregar columnas de vales
            for d in DENOMINACIONES:
                col_name = f"vale_{d}"
                if col_name in df_filtrado.columns:
                    agg_dict[col_name] = "sum"  # Sumar los vales
            
            try:
                df_mostrar = df_filtrado.groupby(columnas_agrupacion).agg(agg_dict).reset_index()
            except Exception as e:
                st.warning(f"Error al agrupar datos: {e}")
                df_mostrar = df_filtrado
        else:
            df_mostrar = df_filtrado
    else:
        # Para "Todas" las fechas, agrupar por dependencia sumando todo
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
            if "total_entregado" in df_filtrado.columns:
                agg_dict["total_entregado"] = "sum"
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
    
    if mostrar_planilla:
        st.markdown("---")
        
        total_general = df_mostrar["total_entregado"].sum() if "total_entregado" in df_mostrar.columns else 0
        
        st.markdown(f"""
        <div class="planilla-separacion">
            <h3>📋 PLANILLA DE SEPARACIÓN DE VALES</h3>
            <p><strong>Fecha:</strong> {fecha_seleccionada if fecha_seleccionada != "Todas" else "Todas las fechas"}</p>
            <p><strong>Total a distribuir:</strong> ${total_general:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar cada dependencia con sus vales - USANDO DATOS GUARDADOS
        for idx, row in df_mostrar.iterrows():
            cuota = row['cuota_objetivo'] if 'cuota_objetivo' in row else 0
            total_entregado = row['total_entregado'] if 'total_entregado' in row else 0
            
            # Calcular el total en vales a partir de los datos guardados
            total_vales = 0
            for denom in DENOMINACIONES:
                col_name = f"vale_{denom}"
                if col_name in row:
                    cantidad = int(row[col_name]) if pd.notnull(row[col_name]) else 0
                    total_vales += cantidad * denom
            
            nombre_dependencia = row['dependencia_nombre'] if 'dependencia_nombre' in row else "Sin nombre"
            
            # Verificar si coincide
            coincide = abs(total_vales - total_entregado) <= 100
            
            st.markdown(f"""
            <div class="planilla-separacion">
                <div class="dependencia-item" style="border-left: 4px solid {'#28a745' if coincide else '#dc3545'};">
                    <strong>{nombre_dependencia}</strong>
                    <br>
                    <span style="color: #6c757d;">Cuota:</span> <strong>${cuota:,.0f}</strong> | 
                    <span style="color: #6c757d;">Entregado:</span> <strong>${total_entregado:,.0f}</strong>
                    <br>
                    <span style="color: #6c757d;">Vales a entregar:</span>
                </div>
            """, unsafe_allow_html=True)
            
            # Mostrar vales en columnas
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
            
            # Mostrar total de la dependencia
            st.markdown(f"""
                <div style="text-align: right; font-weight: bold; margin-top: 10px; 
                           padding-top: 10px; border-top: 2px solid #dee2e6;">
                    <strong>Total en vales: ${total_mostrado:,.0f}</strong>
                </div>
                <div style="text-align: right; color: {'#28a745' if coincide else '#dc3545'}; 
                           margin-bottom: 10px;">
                    {'✅ Coincide con entregado' if coincide else f'⚠️ Diferencia: ${abs(total_entregado - total_mostrado):,.0f}'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Botón para descargar planilla
        if st.button("📥 Descargar planilla completa (CSV)"):
            try:
                df_planilla = df_mostrar.copy()
                columnas_renombrar = {
                    "dependencia_nombre": "Dependencia",
                    "cuota_objetivo": "Cuota",
                    "total_entregado": "Total_Entregado"
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
        # Mostrar como tabla normal
        st.subheader("📊 Detalle de Distribución")
        
        columnas_mostrar = []
        if "fecha" in df_mostrar.columns:
            columnas_mostrar.append("fecha")
        if "dependencia_nombre" in df_mostrar.columns:
            columnas_mostrar.append("dependencia_nombre")
        if "cuota_objetivo" in df_mostrar.columns:
            columnas_mostrar.append("cuota_objetivo")
        if "total_entregado" in df_mostrar.columns:
            columnas_mostrar.append("total_entregado")
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
