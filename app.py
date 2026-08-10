import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import calendar
import time
import re

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

DENOMINACIONES = [20000, 10000, 3000, 2000, 1000, 500, 100]

def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def limpiar_numero(valor):
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    valor_str = str(valor).strip()
    if not valor_str:
        return 0
    valor_str = re.sub(r'[^\d.]', '', valor_str)
    if not valor_str:
        return 0
    try:
        return int(float(valor_str))
    except:
        return 0

def calcular_total_caja(stock):
    total = 0
    for denom, cantidad in stock.items():
        total += denom * cantidad
    return total

def verificar_login(username, password):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("usuarios")
        datos = ws.get_all_records()
        for user in datos:
            if str(user["username"]).strip() == str(username).strip() and str(user["password_hash"]).strip() == str(password).strip():
                return True
        return False
    except Exception as e:
        st.error(f"Error de login: {e}")
        return False

def contar_miercoles(anio, mes):
    count = 0
    for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
        if calendar.weekday(anio, mes, dia) == 2:
            count += 1
    return count

def obtener_dependencias():
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("dependencias")
        datos = ws.get_all_records()
        hoy = date.today()
        
        dependencias = []
        for d in datos:
            año_dato = limpiar_numero(d.get("año", 0))
            mes_dato = limpiar_numero(d.get("mes", 0))
            monto = limpiar_numero(d.get("monto_mensual", 0))
            nombre = str(d.get("nombre", "")).strip()
            
            if año_dato == hoy.year and mes_dato == hoy.month:
                dependencias.append({
                    "id": limpiar_numero(d.get("dependencia_id", 0)),
                    "nombre": nombre,
                    "monto_mensual": monto
                })
        return dependencias
    except Exception as e:
        st.error(f"Error al leer dependencias: {e}")
        return []

def obtener_stock_actual():
    """Lee stock usando las columnas A y B directamente"""
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        
        todos_los_datos = ws.get_all_values()
        
        st.write("### 🔍 Depuración - Datos crudos de 'vales_disponibles'")
        st.write(f"**Total de filas leídas:** {len(todos_los_datos)}")
        
        if todos_los_datos:
            st.write("**Primeras 5 filas (para depuración):**")
            df_crudo = pd.DataFrame(todos_los_datos[:5])
            st.dataframe(df_crudo)
        
        stock = {den: 0 for den in DENOMINACIONES}
        
        for idx, fila in enumerate(todos_los_datos):
            if len(fila) >= 2:
                col_a = str(fila[0]).strip() if fila[0] else ""
                col_b = str(fila[1]).strip() if len(fila) > 1 and fila[1] else ""
                
                if not col_a or col_a.lower() in ["denominacion", "denominación", "cantidad", "denomination"]:
                    continue
                
                denom_limpio = limpiar_numero(col_a)
                cantidad = limpiar_numero(col_b)
                
                if denom_limpio in stock:
                    stock[denom_limpio] = cantidad
        
        st.write(f"**✅ Stock final:** {stock}")
        return stock
    except Exception as e:
        st.error(f"Error al leer stock: {e}")
        return {den: 0 for den in DENOMINACIONES}

def actualizar_stock(stock_nuevo):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        
        for denom, cantidad in stock_nuevo.items():
            cell = ws.find(str(denom))
            if cell:
                ws.update_cell(cell.row, 2, cantidad)
                time.sleep(0.1)
        return True
    except Exception as e:
        st.error(f"Error al actualizar stock: {e}")
        return False

def agregar_vales(vales_ingreso):
    stock_actual = obtener_stock_actual()
    for denom, cantidad in vales_ingreso.items():
        if cantidad > 0:
            stock_actual[denom] += cantidad
    actualizar_stock(stock_actual)
    return stock_actual

def cambiar_vales(desde_denom, desde_cant, hasta_denom, hasta_cant):
    try:
        stock_actual = obtener_stock_actual()
        if stock_actual[desde_denom] < desde_cant:
            return False, f"No hay suficientes vales de ${desde_denom:,.0f}"
        stock_actual[desde_denom] -= desde_cant
        stock_actual[hasta_denom] += hasta_cant
        actualizar_stock(stock_actual)
        return True, "Cambio exitoso"
    except Exception as e:
        return False, f"Error: {e}"

def registrar_entrega_detallada(fecha, reparto, tipo):
    try:
        sheet = conectar_gsheets()
        try:
            detalle_ws = sheet.worksheet("detalle_entregas")
        except:
            detalle_ws = sheet.add_worksheet(title="detalle_entregas", rows="1000", cols="15")
            encabezados = ["fecha", "dependencia_id", "dependencia_nombre", "cuota_objetivo", "total_entregado"]
            for d in DENOMINACIONES:
                encabezados.append(f"vale_{d}")
            detalle_ws.append_row(encabezados)
        for ofi in reparto:
            nueva_fila = [str(fecha), ofi.get("id", 0), ofi["nombre"], ofi.get("cuota_objetivo", 0), ofi["total"]]
            for j, denom in enumerate(DENOMINACIONES):
                nueva_fila.append(ofi["vales"][j])
            detalle_ws.append_row(nueva_fila)
            time.sleep(0.05)
        return True
    except Exception as e:
        st.error(f"Error al registrar detalle: {e}")
        return False

def distribuir_vales_auto(dependencias, stock_actual, miercoles):
    reparto = []
    for dep in dependencias:
        cuota_semanal = dep["monto_mensual"] / miercoles
        reparto.append({
            "id": dep["id"],
            "nombre": dep["nombre"],
            "cuota_objetivo": cuota_semanal,
            "vales": [0, 0, 0, 0, 0, 0, 0],
            "total": 0
        })
    stock = stock_actual.copy()
    
    def calcular_combinacion_exacta(monto, stock_disponible):
        combinacion = [0, 0, 0, 0, 0, 0, 0]
        resto = monto
        for j, valor_vale in enumerate(DENOMINACIONES):
            if resto <= 0:
                break
            if stock_disponible[valor_vale] > 0:
                max_posibles = min(stock_disponible[valor_vale], resto // valor_vale)
                if max_posibles > 0:
                    usar = max_posibles
                    if j < len(DENOMINACIONES) - 1:
                        siguiente_valor = DENOMINACIONES[j + 1]
                        resto_despues = resto - (usar * valor_vale)
                        if resto_despues > 0 and resto_despues % siguiente_valor != 0:
                            usar = max(0, usar - 1)
                    combinacion[j] = usar
                    resto -= usar * valor_vale
        for j, valor_vale in enumerate(DENOMINACIONES):
            if resto <= 0:
                break
            if stock_disponible[valor_vale] > combinacion[j]:
                disponibles = stock_disponible[valor_vale] - combinacion[j]
                if resto >= valor_vale:
                    necesarios = min(disponibles, resto // valor_vale)
                    combinacion[j] += necesarios
                    resto -= necesarios * valor_vale
        return combinacion, resto
    
    for ofi in reparto:
        monto_necesario = ofi["cuota_objetivo"]
        combinacion, resto = calcular_combinacion_exacta(monto_necesario, stock)
        ofi["vales"] = combinacion
        ofi["total"] = monto_necesario - resto
        for j, valor_vale in enumerate(DENOMINACIONES):
            stock[valor_vale] -= combinacion[j]
    return reparto, stock

def registrar_historial(fecha, reparto, tipo, es_ingreso=False, vales_ingresados=None):
    try:
        sheet = conectar_gsheets()
        try:
            historial_ws = sheet.worksheet("entregas_semanales")
        except:
            historial_ws = sheet.add_worksheet(title="entregas_semanales", rows="1000", cols="20")
        if es_ingreso and vales_ingresados:
            nueva_fila = [str(fecha), 0, vales_ingresados.get(100, 0), vales_ingresados.get(500, 0), vales_ingresados.get(1000, 0), vales_ingresados.get(2000, 0), vales_ingresados.get(3000, 0), vales_ingresados.get(10000, 0), vales_ingresados.get(20000, 0), f"INGRESO - {tipo}"]
        else:
            totales = [0, 0, 0, 0, 0, 0, 0]
            for ofi in reparto:
                totales[0] += ofi["vales"][6]
                totales[1] += ofi["vales"][5]
                totales[2] += ofi["vales"][4]
                totales[3] += ofi["vales"][3]
                totales[4] += ofi["vales"][2]
                totales[5] += ofi["vales"][1]
                totales[6] += ofi["vales"][0]
            nueva_fila = [str(fecha), 0, totales[0], totales[1], totales[2], totales[3], totales[4], totales[5], totales[6], f"DISTRIBUCION - {tipo}"]
        historial_ws.append_row(nueva_fila)
        time.sleep(0.05)
        return True
    except Exception as e:
        st.error(f"Error al registrar historial: {e}")
        return False

# ============================================
# INTERFAZ
# ============================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Sistema de Vales")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            st.subheader("Iniciar sesión")
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)
            if submit:
                if verificar_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
else:
    st.title("🎫 Sistema de Gestión de Vales")
    st.sidebar.success(f"✅ Usuario: {st.session_state.username}")
    
    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state.logged_in = False
        st.rerun()
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📦 Ingresar Vales", "🔄 Cambiar Vales", "🤖 Distribución Auto", "✏️ Distribución Manual", "💰 Stock Actual", "📜 Historial"])
    
    # ========== TAB 1: INGRESAR VALES ==========
    with tab1:
        st.header("📥 Ingreso de nuevos vales")
        stock_actual = obtener_stock_actual()
        total_caja = calcular_total_caja(stock_actual)
        st.metric("💰 Total en caja", f"${total_caja:,.0f}")
        
        with st.form("ingreso_vales"):
            col1, col2 = st.columns(2)
            with col1:
                v20000 = st.number_input("Vales de $20.000", min_value=0, value=0, step=1)
                v10000 = st.number_input("Vales de $10.000", min_value=0, value=0, step=1)
                v3000 = st.number_input("Vales de $3.000", min_value=0, value=0, step=1)
                v2000 = st.number_input("Vales de $2.000", min_value=0, value=0, step=1)
            with col2:
                v1000 = st.number_input("Vales de $1.000", min_value=0, value=0, step=1)
                v500 = st.number_input("Vales de $500", min_value=0, value=0, step=1)
                v100 = st.number_input("Vales de $100", min_value=0, value=0, step=1)
            fecha_ingreso = st.date_input("Fecha de ingreso", value=date.today())
            total_ingreso = v20000*20000 + v10000*10000 + v3000*3000 + v2000*2000 + v1000*1000 + v500*500 + v100*100
            st.metric("💰 Total a ingresar", f"${total_ingreso:,.0f}")
            if st.form_submit_button("✅ Confirmar Ingreso", type="primary"):
                if total_ingreso > 0:
                    vales_ingreso = {20000: v20000, 10000: v10000, 3000: v3000, 2000: v2000, 1000: v1000, 500: v500, 100: v100}
                    agregar_vales(vales_ingreso)
                    registrar_historial(fecha_ingreso, None, "MANUAL", es_ingreso=True, vales_ingresados=vales_ingreso)
                    st.success(f"✅ Se ingresaron ${total_ingreso:,.0f}")
                    st.rerun()
                else:
                    st.warning("Ingresa al menos un vale")
    
    # ========== TAB 2: CAMBIAR VALES ==========
    with tab2:
        st.header("🔄 Cambiar Vales")
        with st.form("cambio_vales"):
            col1, col2 = st.columns(2)
            with col1:
                desde_denom = st.selectbox("Denominación origen", options=DENOMINACIONES, format_func=lambda x: f"${x:,.0f}")
                desde_cant = st.number_input("Cantidad a sacar", min_value=1, value=1, step=1)
            with col2:
                hasta_denom = st.selectbox("Denominación destino", options=DENOMINACIONES, format_func=lambda x: f"${x:,.0f}")
                hasta_cant = st.number_input("Cantidad a agregar", min_value=1, value=1, step=1)
            if st.form_submit_button("🔄 Ejecutar Cambio", type="primary"):
                if desde_denom == hasta_denom:
                    st.error("No puedes cambiar la misma denominación")
                else:
                    exito, mensaje = cambiar_vales(desde_denom, desde_cant, hasta_denom, hasta_cant)
                    if exito:
                        st.success(mensaje)
                        st.rerun()
                    else:
                        st.error(mensaje)
    
    # ========== TAB 3: DISTRIBUCIÓN AUTOMÁTICA ==========
    with tab3:
        st.header("🤖 Distribución Automática Semanal")
        hoy = date.today()
        dependencias = obtener_dependencias()
        stock = obtener_stock_actual()
        total_caja = calcular_total_caja(stock)
        st.metric("💰 Total en caja", f"${total_caja:,.0f}")
        
        if not dependencias:
            st.warning("⚠️ No hay dependencias para el mes actual")
        else:
            miercoles = contar_miercoles(hoy.year, hoy.month)
            st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
            st.subheader("📊 Dependencias")
            tabla_deps = []
            for dep in dependencias:
                monto_semanal = dep["monto_mensual"] / miercoles
                tabla_deps.append({"ID": dep["id"], "Dependencia": dep["nombre"], "Monto Mensual": f"${dep['monto_mensual']:,.0f}", "Monto Semanal": f"${monto_semanal:,.0f}"})
            st.dataframe(pd.DataFrame(tabla_deps), use_container_width=True)
            st.subheader("💰 Stock Actual")
            stock_df = pd.DataFrame([{"Denominación": f"${d:,.0f}", "Cantidad": stock.get(d, 0)} for d in DENOMINACIONES])
            st.dataframe(stock_df, use_container_width=True)
            fecha_dist = st.date_input("Fecha de distribución (miércoles)", value=hoy)
            if st.button("📦 Calcular Distribución Auto", type="primary"):
                if fecha_dist.weekday() != 2:
                    st.warning("⚠️ La distribución debe hacerse en un miércoles")
                else:
                    reparto, stock_nuevo = distribuir_vales_auto(dependencias, stock, miercoles)
                    st.success("✅ Distribución calculada")
                    datos_tabla = []
                    for ofi in reparto:
                        datos_tabla.append({"Dependencia": ofi["nombre"], "Cuota": f"${ofi['cuota_objetivo']:,.0f}", "Entregado": f"${ofi['total']:,.0f}", "Diferencia": f"${ofi['cuota_objetivo'] - ofi['total']:,.0f}", "$20k": ofi["vales"][0], "$10k": ofi["vales"][1], "$3k": ofi["vales"][2], "$2k": ofi["vales"][3], "$1k": ofi["vales"][4], "$500": ofi["vales"][5], "$100": ofi["vales"][6]})
                    st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True)
                    st.session_state.reparto = reparto
                    st.session_state.stock_nuevo = stock_nuevo
                    st.session_state.fecha_dist = fecha_dist
            if 'reparto' in st.session_state and st.button("✅ Guardar Distribución Auto", type="primary"):
                if actualizar_stock(st.session_state.stock_nuevo):
                    registrar_historial(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                    registrar_entrega_detallada(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                    st.success("🎉 Distribución guardada")
                    st.rerun()
    
    # ========== TAB 4: DISTRIBUCIÓN MANUAL ==========
    with tab4:
        st.header("✏️ Distribución Manual Semanal")
        hoy = date.today()
        dependencias = obtener_dependencias()
        if not dependencias:
            st.warning("No hay dependencias")
        else:
            miercoles = contar_miercoles(hoy.year, hoy.month)
            st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
            stock = obtener_stock_actual()
            total_caja = calcular_total_caja(stock)
            st.metric("💰 Total en caja", f"${total_caja:,.0f}")
            st.subheader("💰 Stock Disponible")
            stock_df = pd.DataFrame([{"Denominación": f"${d:,.0f}", "Cantidad": stock.get(d, 0)} for d in DENOMINACIONES])
            st.dataframe(stock_df, use_container_width=True)
            
            if 'manual_asignaciones' not in st.session_state:
                st.session_state.manual_asignaciones = {}
            
            reparto_manual = []
            for dep in dependencias:
                cuota = dep["monto_mensual"] / miercoles
                st.markdown(f"### {dep['nombre']} - Cuota: ${cuota:,.0f}")
                cols = st.columns(7)
                vales_asignados = []
                total_asignado = 0
                for i, denom in enumerate(DENOMINACIONES):
                    with cols[i]:
                        key = f"{dep['id']}_{denom}"
                        cantidad = st.number_input(f"${denom:,.0f}", min_value=0, value=st.session_state.manual_asignaciones.get(key, 0), step=1, key=key)
                        vales_asignados.append(cantidad)
                        total_asignado += cantidad * denom
                st.metric("Total asignado", f"${total_asignado:,.0f}")
                reparto_manual.append({"id": dep["id"], "nombre": dep["nombre"], "cuota_objetivo": cuota, "vales": vales_asignados, "total": total_asignado})
            
            if st.button("✅ Guardar Distribución Manual", type="primary"):
                stock_temp = stock.copy()
                for ofi in reparto_manual:
                    for j, denom in enumerate(DENOMINACIONES):
                        if ofi["vales"][j] > stock_temp.get(denom, 0):
                            st.error(f"No hay suficientes vales de ${denom:,.0f}")
                            st.stop()
                        stock_temp[denom] -= ofi["vales"][j]
                actualizar_stock(stock_temp)
                registrar_historial(date.today(), reparto_manual, "MANUAL")
                registrar_entrega_detallada(date.today(), reparto_manual, "MANUAL")
                st.success("Distribución guardada")
                st.rerun()
    
    # ========== TAB 5: STOCK ACTUAL ==========
    with tab5:
        st.header("💰 Stock Actual de Vales")
        if st.button("🔄 Refrescar stock"):
            st.rerun()
        stock = obtener_stock_actual()
        total_caja = calcular_total_caja(stock)
        stock_display = pd.DataFrame([{"Denominación": f"${d:,.0f}", "Cantidad": stock.get(d, 0), "Total": f"${d * stock.get(d, 0):,.0f}"} for d in DENOMINACIONES])
        st.dataframe(stock_display, use_container_width=True)
        st.metric("💵 Total en caja", f"${total_caja:,.0f}")
    
    # ========== TAB 6: HISTORIAL ==========
    with tab6:
        st.header("📜 Historial")
        try:
            sheet = conectar_gsheets()
            historial_ws = sheet.worksheet("entregas_semanales")
            historial_datos = historial_ws.get_all_records()
            if historial_datos:
                st.dataframe(pd.DataFrame(historial_datos).tail(30), use_container_width=True)
        except:
            st.info("No hay historial")
