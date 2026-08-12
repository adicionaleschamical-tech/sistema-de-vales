import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import calendar
import time
import re
import io
import base64

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

DENOMINACIONES = [20000, 10000, 3000, 2000, 1000, 500, 100]

# ============================================
# CONFIGURACIÓN DE ESTILO
# ============================================

def aplicar_estilo():
    """Aplica estilos CSS personalizados"""
    st.markdown("""
    <style>
        /* Tarjetas */
        .card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }
        .card-dark {
            background-color: #2d2d2d;
            color: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            margin-bottom: 15px;
        }
        /* Badges */
        .badge-success {
            background-color: #28a745;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        .badge-danger {
            background-color: #dc3545;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        .badge-warning {
            background-color: #ffc107;
            color: #212529;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        /* Dashboard stats */
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-card-green {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        .stat-card-red {
            background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%);
        }
        .stat-card-blue {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        }
        /* Títulos */
        .main-title {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
    </style>
    """, unsafe_allow_html=True)

def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def limpiar_numero(valor):
    """Limpia y convierte números de diferentes formatos a enteros"""
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    
    valor_str = str(valor).strip()
    if not valor_str:
        return 0
    
    # Eliminar símbolos de moneda y espacios
    valor_str = valor_str.replace("$", "").replace("$ ", "").replace(" ", "").strip()
    
    if not valor_str:
        return 0
    
    # Manejar diferentes formatos de números
    try:
        # Si tiene coma y punto
        if "," in valor_str and "." in valor_str:
            # Formato chileno/europeo: 1.234.567,89
            if valor_str.rfind(",") > valor_str.rfind("."):
                valor_str = valor_str.replace(".", "").replace(",", ".")
            # Formato americano: 1,234,567.89
            else:
                valor_str = valor_str.replace(",", "")
        
        # Si solo tiene coma
        elif "," in valor_str:
            partes = valor_str.split(",")
            # Si es decimal (ej: 900,50 o 900,5)
            if len(partes) == 2 and len(partes[1]) <= 2:
                valor_str = valor_str.replace(",", ".")
            # Si es separador de miles (ej: 900,000 o 1,000,000)
            else:
                valor_str = valor_str.replace(",", "")
        
        # Si solo tiene punto
        elif "." in valor_str:
            partes = valor_str.split(".")
            # Si es decimal (ej: 900.50 o 900.5)
            if len(partes) == 2 and len(partes[1]) <= 2:
                valor_str = valor_str.replace(".", ",").replace(",", ".")
            # Si es separador de miles (ej: 900.000 o 1.000.000)
            else:
                valor_str = valor_str.replace(".", "")
        
        # Intentar convertir a entero
        if "." in valor_str:
            return int(float(valor_str))
        else:
            return int(valor_str)
            
    except (ValueError, TypeError):
        # Si falla la conversión, intentar extraer solo números
        try:
            numeros = re.findall(r'\d+', str(valor))
            if numeros:
                return int(''.join(numeros))
        except:
            pass
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

def obtener_dependencias(anio=None, mes=None):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("dependencias")
        datos = ws.get_all_records()
        if anio is None or mes is None:
            hoy = date.today()
            anio = hoy.year
            mes = hoy.month
        dependencias = []
        for d in datos:
            año_dato = limpiar_numero(d.get("año", 0))
            mes_dato = limpiar_numero(d.get("mes", 0))
            monto = limpiar_numero(d.get("monto_mensual", 0))
            nombre = str(d.get("nombre", "")).strip()
            if nombre and año_dato == anio and mes_dato == mes:
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
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        todos_los_datos = ws.get_all_values()
        stock = {den: 0 for den in DENOMINACIONES}
        for fila in todos_los_datos:
            if len(fila) >= 2:
                col_a = str(fila[0]).strip() if fila[0] else ""
                col_b = str(fila[1]).strip() if len(fila) > 1 and fila[1] else ""
                if not col_a or col_a.lower() in ["denominacion", "denominación", "cantidad", "denomination"]:
                    continue
                denom_limpio = limpiar_numero(col_a)
                cantidad = limpiar_numero(col_b)
                if denom_limpio in stock:
                    stock[denom_limpio] = cantidad
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
        registrar_cambio_historial(desde_denom, desde_cant, hasta_denom, hasta_cant)
        return True, "Cambio exitoso"
    except Exception as e:
        return False, f"Error: {e}"

def registrar_cambio_historial(desde_denom, desde_cant, hasta_denom, hasta_cant):
    try:
        sheet = conectar_gsheets()
        try:
            cambios_ws = sheet.worksheet("cambios_vales")
        except:
            cambios_ws = sheet.add_worksheet(title="cambios_vales", rows="1000", cols="10")
            cambios_ws.append_row(["fecha", "desde_denominacion", "desde_cantidad", "hasta_denominacion", "hasta_cantidad", "descripcion"])
        nueva_fila = [str(date.today()), desde_denom, desde_cant, hasta_denom, hasta_cant, f"Cambio: {desde_cant} x ${desde_denom} por {hasta_cant} x ${hasta_denom}"]
        cambios_ws.append_row(nueva_fila)
        return True
    except Exception as e:
        return False

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
# FUNCIONES DE MEJORAS
# ============================================

def mostrar_dashboard(dependencias, stock, total_caja, miercoles):
    """Mejora 3: Resumen ejecutivo / Dashboard"""
    st.markdown("---")
    st.subheader("📊 Dashboard Ejecutivo")
    
    total_mensual = sum(dep["monto_mensual"] for dep in dependencias)
    total_semanal = sum(dep["monto_mensual"] / miercoles for dep in dependencias)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <h3>${total_caja:,.0f}</h3>
            <p>💰 Total en Caja</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="stat-card stat-card-green">
            <h3>${total_mensual:,.0f}</h3>
            <p>📅 Total Mensual</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="stat-card stat-card-blue">
            <h3>${total_semanal:,.0f}</h3>
            <p>📊 Total Semanal</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        diferencia = total_caja - total_semanal
        color = "stat-card-green" if diferencia >= 0 else "stat-card-red"
        st.markdown(f"""
        <div class="stat-card {color}">
            <h3>${diferencia:,.0f}</h3>
            <p>{'✅ Disponible' if diferencia >= 0 else '⚠️ Faltante'}</p>
        </div>
        """, unsafe_allow_html=True)

def mostrar_graficos(reparto):
    """Mejora 6: Gráficos de distribución"""
    try:
        import plotly.express as px
        
        st.subheader("📈 Gráfico de Distribución")
        
        df_grafico = pd.DataFrame([
            {"Dependencia": ofi["nombre"], "Total Entregado": ofi["total"], "Cuota": ofi["cuota_objetivo"]}
            for ofi in reparto
        ])
        
        fig = px.bar(df_grafico, x="Dependencia", y=["Total Entregado", "Cuota"],
                     title="Distribución por Dependencia",
                     barmode="group",
                     color_discrete_sequence=["#667eea", "#38ef7d"])
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.info("📊 Instala plotly para ver gráficos: pip install plotly")

def descargar_reporte_csv(reparto, fecha):
    """Mejora 7: Reporte descargable en CSV"""
    if reparto:
        df = pd.DataFrame(reparto)
        csv = df.to_csv(index=False).encode('utf-8')
        b64 = base64.b64encode(csv).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="distribucion_{fecha}.csv">⬇️ Descargar Reporte CSV</a>'
        st.markdown(href, unsafe_allow_html=True)

def simular_notificacion(mensaje):
    """Mejora 10: Notificaciones simuladas"""
    st.success(f"📧 {mensaje}")

# ============================================
# INTERFAZ PRINCIPAL
# ============================================

# Aplicar estilos
aplicar_estilo()

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
    st.markdown('<p class="main-title">🎫 Sistema de Gestión de Vales</p>', unsafe_allow_html=True)
    st.sidebar.success(f"✅ Usuario: {st.session_state.username}")
    
    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state.logged_in = False
        st.rerun()
    
    # ========== SELECTOR DE MES/AÑO ==========
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Seleccionar Mes")
    
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    hoy = date.today()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    mes_seleccionado = st.sidebar.selectbox("Mes", options=range(1, 13), 
                                            format_func=lambda x: meses[x-1],
                                            index=mes_actual-1)
    año_seleccionado = st.sidebar.number_input("Año", min_value=2020, max_value=2030, value=año_actual)
    
    # ========== MODO OSCURO ========== (Mejora 8)
    st.sidebar.markdown("---")
    modo_oscuro = st.sidebar.toggle("🌙 Modo Oscuro", value=False)
    if modo_oscuro:
        st.markdown("""
        <style>
            .stApp {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            .stDataFrame {
                background-color: #16213e;
                color: #ffffff;
            }
            .stMetric {
                background-color: #16213e;
                border-radius: 10px;
                padding: 10px;
            }
            .card {
                background-color: #16213e;
                color: #ffffff;
            }
            .main-title {
                color: #ffffff !important;
                -webkit-text-fill-color: #ffffff !important;
            }
        </style>
        """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"📆 Mostrando datos de {meses[mes_seleccionado-1]} {año_seleccionado}")
    
    # ========== TABS ==========
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
                    simular_notificacion(f"Ingreso de ${total_ingreso:,.0f} registrado correctamente")
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
                        simular_notificacion(f"Cambio de vales registrado: {mensaje}")
                        st.rerun()
                    else:
                        st.error(mensaje)
    
    # ========== TAB 3: DISTRIBUCIÓN AUTOMÁTICA ==========
    with tab3:
        st.header("🤖 Distribución Automática Semanal")
        
        dependencias = obtener_dependencias(año_seleccionado, mes_seleccionado)
        stock = obtener_stock_actual()
        total_caja = calcular_total_caja(stock)
        miercoles = contar_miercoles(año_seleccionado, mes_seleccionado)
        
        if dependencias:
            mostrar_dashboard(dependencias, stock, total_caja, miercoles)
        
        if not dependencias:
            st.warning(f"⚠️ No hay dependencias para {meses[mes_seleccionado-1]} {año_seleccionado}")
        else:
            st.info(f"📆 {meses[mes_seleccionado-1]} {año_seleccionado} tiene **{miercoles} miércoles**")
            
            st.subheader("📊 Dependencias")
            tabla_deps = []
            for dep in dependencias:
                monto_semanal = dep["monto_mensual"] / miercoles
                tabla_deps.append({"ID": dep["id"], "Dependencia": dep["nombre"], "Monto Mensual": f"${dep['monto_mensual']:,.0f}", "Monto Semanal": f"${monto_semanal:,.0f}"})
            st.dataframe(pd.DataFrame(tabla_deps), use_container_width=True)
            
            st.subheader("💰 Stock Actual")
            stock_df = pd.DataFrame([{"Denominación": f"${d:,.0f}", "Cantidad": stock.get(d, 0)} for d in DENOMINACIONES])
            st.dataframe(stock_df, use_container_width=True)
            
            fecha_dist = st.date_input("Fecha de distribución (miércoles)", value=date.today())
            if st.button("📦 Calcular Distribución Auto", type="primary"):
                if fecha_dist.weekday() != 2:
                    st.warning("⚠️ La distribución debe hacerse en un miércoles")
                else:
                    reparto, stock_nuevo = distribuir_vales_auto(dependencias, stock, miercoles)
                    st.success("✅ Distribución calculada")
                    
                    # Mostrar gráficos (Mejora 6)
                    mostrar_graficos(reparto)
                    
                    datos_tabla = []
                    for ofi in reparto:
                        datos_tabla.append({"Dependencia": ofi["nombre"], "Cuota": f"${ofi['cuota_objetivo']:,.0f}", "Entregado": f"${ofi['total']:,.0f}", "Diferencia": f"${ofi['cuota_objetivo'] - ofi['total']:,.0f}", "$20k": ofi["vales"][0], "$10k": ofi["vales"][1], "$3k": ofi["vales"][2], "$2k": ofi["vales"][3], "$1k": ofi["vales"][4], "$500": ofi["vales"][5], "$100": ofi["vales"][6]})
                    st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True)
                    
                    # Reporte descargable (Mejora 7)
                    descargar_reporte_csv(reparto, fecha_dist.strftime("%Y-%m-%d"))
                    
                    st.session_state.reparto = reparto
                    st.session_state.stock_nuevo = stock_nuevo
                    st.session_state.fecha_dist = fecha_dist
            
            # Confirmación antes de guardar (Mejora 4)
            if 'reparto' in st.session_state:
                with st.container():
                    st.markdown("---")
                    st.subheader("📋 Confirmar Distribución")
                    st.info("Revisa el resumen antes de guardar:")
                    
                    # Mostrar resumen
                    total_entregado = sum(ofi["total"] for ofi in st.session_state.reparto)
                    total_cuotas = sum(ofi["cuota_objetivo"] for ofi in st.session_state.reparto)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total a entregar", f"${total_entregado:,.0f}")
                    with col2:
                        st.metric("Total cuotas", f"${total_cuotas:,.0f}")
                    with col3:
                        st.metric("Diferencia", f"${total_cuotas - total_entregado:,.0f}")
                    
                    if st.button("✅ Confirmar y Guardar Distribución", type="primary"):
                        if actualizar_stock(st.session_state.stock_nuevo):
                            registrar_historial(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                            registrar_entrega_detallada(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                            st.success("🎉 Distribución guardada exitosamente")
                            simular_notificacion(f"Distribución del {st.session_state.fecha_dist.strftime('%d/%m/%Y')} guardada")
                            del st.session_state.reparto
                            del st.session_state.stock_nuevo
                            del st.session_state.fecha_dist
                            st.rerun()
    
    # ========== TAB 4: DISTRIBUCIÓN MANUAL ==========
    with tab4:
        st.header("✏️ Distribución Manual Semanal")
        
        dependencias = obtener_dependencias(año_seleccionado, mes_seleccionado)
        if not dependencias:
            st.warning(f"No hay dependencias para {meses[mes_seleccionado-1]} {año_seleccionado}")
        else:
            miercoles = contar_miercoles(año_seleccionado, mes_seleccionado)
            st.info(f"📆 {meses[mes_seleccionado-1]} {año_seleccionado} tiene **{miercoles} miércoles**")
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
            else:
                st.info("No hay historial")
        except:
            st.info("No hay historial")
