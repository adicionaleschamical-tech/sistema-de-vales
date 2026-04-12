import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date, datetime
import calendar

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
    valor_str = valor_str.replace(".", "").replace(" ", "").replace("$", "").replace(",", "")
    try:
        return int(float(valor_str))
    except:
        return 0

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
        st.error(f"Error: {e}")
        return False

def contar_miercoles(anio, mes):
    count = 0
    for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
        if calendar.weekday(anio, mes, dia) == 2:
            count += 1
    return count

def obtener_dependencias():
    sheet = conectar_gsheets()
    ws = sheet.worksheet("dependencias")
    datos = ws.get_all_records()
    hoy = date.today()
    
    dependencias = []
    for d in datos:
        año_dato = limpiar_numero(d.get("año", 0))
        mes_dato = limpiar_numero(d.get("mes", 0))
        
        if año_dato == hoy.year and mes_dato == hoy.month:
            monto = limpiar_numero(d.get("monto_mensual", 0))
            dependencias.append({
                "id": limpiar_numero(d.get("dependencia_id", 0)),
                "nombre": str(d.get("nombre", "")),
                "monto_mensual": monto
            })
    return dependencias

def obtener_stock_actual():
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    datos = ws.get_all_records()
    
    stock = {den: 0 for den in DENOMINACIONES}
    for row in datos:
        denom = limpiar_numero(row.get("denominacion", 0))
        cantidad = limpiar_numero(row.get("cantidad", 0))
        if denom in stock:
            stock[denom] = cantidad
    return stock

def actualizar_stock(stock_nuevo):
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    
    for denom, cantidad in stock_nuevo.items():
        celda = ws.find(str(denom))
        if celda:
            ws.update_cell(celda.row, 2, cantidad)

def agregar_vales(vales_ingreso):
    stock_actual = obtener_stock_actual()
    for denom, cantidad in vales_ingreso.items():
        if cantidad > 0:
            stock_actual[denom] += cantidad
    actualizar_stock(stock_actual)
    return stock_actual

def distribuir_vales(dependencias, stock_actual, miercoles):
    """Distribuye vales de manera SURTIDA (diferentes denominaciones)"""
    reparto = []
    for dep in dependencias:
        cuota_semanal = dep["monto_mensual"] / miercoles
        reparto.append({
            "nombre": dep["nombre"],
            "cuota_objetivo": cuota_semanal,
            "vales": [0, 0, 0, 0, 0, 0, 0],
            "total": 0
        })
    
    stock = stock_actual.copy()
    num_dependencias = len(reparto)
    
    # Primera pasada: distribuir equitativamente cada denominación
    for j, valor_vale in enumerate(DENOMINACIONES):
        if stock[valor_vale] == 0:
            continue
        
        disponibles = stock[valor_vale]
        vales_por_dependencia = disponibles // num_dependencias
        resto = disponibles % num_dependencias
        
        for i, ofi in enumerate(reparto):
            cuota_restante = ofi["cuota_objetivo"] - ofi["total"]
            max_posible = int(cuota_restante // valor_vale)
            
            a_asignar = vales_por_dependencia
            if i < resto:
                a_asignar += 1
            a_asignar = min(a_asignar, max_posible)
            
            if a_asignar > 0:
                ofi["vales"][j] = a_asignar
                ofi["total"] += a_asignar * valor_vale
                stock[valor_vale] -= a_asignar
    
    # Segunda pasada: repartir los sobrantes a los que más falta les hace
    for j, valor_vale in enumerate(DENOMINACIONES):
        if stock[valor_vale] == 0:
            continue
        
        reparto_ordenado = sorted(enumerate(reparto), key=lambda x: x[1]["cuota_objetivo"] - x[1]["total"], reverse=True)
        
        for idx, ofi in reparto_ordenado:
            if stock[valor_vale] == 0:
                break
            cuota_restante = ofi["cuota_objetivo"] - ofi["total"]
            if cuota_restante >= valor_vale:
                ofi["vales"][j] += 1
                ofi["total"] += valor_vale
                stock[valor_vale] -= 1
    
    return reparto, stock

def registrar_historial(fecha, reparto, tipo, es_ingreso=False, vales_ingresados=None):
    sheet = conectar_gsheets()
    
    try:
        historial_ws = sheet.worksheet("entregas_semanales")
    except:
        historial_ws = sheet.add_worksheet(title="entregas_semanales", rows="1000", cols="20")
    
    if es_ingreso and vales_ingresados:
        nueva_fila = [
            str(fecha),
            vales_ingresados.get(20000, 0),
            vales_ingresados.get(10000, 0),
            vales_ingresados.get(3000, 0),
            vales_ingresados.get(2000, 0),
            vales_ingresados.get(1000, 0),
            vales_ingresados.get(500, 0),
            vales_ingresados.get(100, 0),
            sum(vales_ingresados.values()),
            f"INGRESO - {tipo}"
        ]
    else:
        totales = [0, 0, 0, 0, 0, 0, 0]
        for ofi in reparto:
            for j, cant in enumerate(ofi["vales"]):
                totales[j] += cant
        nueva_fila = [
            str(fecha),
            totales[0], totales[1], totales[2], totales[3], totales[4], totales[5], totales[6],
            sum(totales),
            f"DISTRIBUCION - {tipo}"
        ]
    
    historial_ws.append_row(nueva_fila)

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
    
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Ingresar Vales", "🎯 Distribución Semanal", "💰 Stock Actual", "📜 Historial"])
    
    # TAB 1: INGRESAR VALES
    with tab1:
        st.header("📥 Ingreso de nuevos vales")
        
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
                    st.success(f"✅ Se ingresaron ${total_ingreso:,.0f} en vales")
                    st.rerun()
                else:
                    st.warning("Ingresa al menos un vale")
    
    # TAB 2: DISTRIBUCIÓN
    with tab2:
        st.header("🎯 Distribución Semanal de Vales")
        
        hoy = date.today()
        dependencias = obtener_dependencias()
        
        if not dependencias:
            st.warning("No hay dependencias para el mes actual")
        else:
            miercoles = contar_miercoles(hoy.year, hoy.month)
            st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
            
            st.subheader("📊 Dependencias")
            tabla_deps = []
            for dep in dependencias:
                monto_semanal = dep["monto_mensual"] / miercoles
                tabla_deps.append({
                    "ID": dep["id"],
                    "Dependencia": dep["nombre"],
                    "Monto Mensual": f"${dep['monto_mensual']:,.0f}",
                    "Monto Semanal": f"${monto_semanal:,.0f}"
                })
            st.dataframe(pd.DataFrame(tabla_deps), use_container_width=True)
            
            stock = obtener_stock_actual()
            st.subheader("💰 Stock Actual")
            stock_df = pd.DataFrame([
                {"Denominación": f"${d:,.0f}", "Cantidad": stock[d]}
                for d in DENOMINACIONES
            ])
            st.dataframe(stock_df, use_container_width=True)
            
            st.markdown("---")
            fecha_dist = st.date_input("Fecha de distribución (miércoles)", value=hoy, key="fecha_dist")
            
            if st.button("📦 Calcular Distribución", type="primary"):
                if fecha_dist.weekday() != 2:
                    st.warning("⚠️ La distribución debe hacerse en un miércoles")
                else:
                    reparto, stock_nuevo = distribuir_vales(dependencias, stock, miercoles)
                    st.success("✅ Distribución calculada")
                    
                    datos_tabla = []
                    for ofi in reparto:
                        datos_tabla.append({
                            "Dependencia": ofi["nombre"],
                            "Cuota": f"${ofi['cuota_objetivo']:,.0f}",
                            "Entregado": f"${ofi['total']:,.0f}",
                            "Diferencia": f"${ofi['cuota_objetivo'] - ofi['total']:,.0f}",
                            "$20k": ofi["vales"][0],
                            "$10k": ofi["vales"][1],
                            "$3k": ofi["vales"][2],
                            "$2k": ofi["vales"][3],
                            "$1k": ofi["vales"][4],
                            "$500": ofi["vales"][5],
                            "$100": ofi["vales"][6],
                        })
                    st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True)
                    
                    if st.button("✅ Confirmar y Guardar Distribución"):
                        actualizar_stock(stock_nuevo)
                        registrar_historial(fecha_dist, reparto, "AUTO")
                        st.success("🎉 Distribución guardada")
                        st.rerun()
    
    # TAB 3: STOCK
    with tab3:
        st.header("💰 Stock Actual de Vales")
        stock = obtener_stock_actual()
        total_dinero = sum(den * stock[den] for den in DENOMINACIONES)
        
        stock_display = pd.DataFrame([
            {"Denominación": f"${d:,.0f}", "Cantidad": stock[d], "Total": f"${d * stock[d]:,.0f}"}
            for d in DENOMINACIONES
        ])
        st.dataframe(stock_display, use_container_width=True)
        st.metric("💵 Total en caja", f"${total_dinero:,.0f}")
    
    # TAB 4: HISTORIAL
    with tab4:
        st.header("📜 Historial de Movimientos")
        try:
            sheet = conectar_gsheets()
            historial_ws = sheet.worksheet("entregas_semanales")
            historial_datos = historial_ws.get_all_records()
            if historial_datos:
                st.dataframe(pd.DataFrame(historial_datos).tail(20), use_container_width=True)
            else:
                st.info("No hay movimientos registrados")
        except:
            st.info("No hay historial disponible")
