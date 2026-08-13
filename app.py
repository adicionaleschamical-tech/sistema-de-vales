import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import time
import re
import io
import base64

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

DENOMINACIONES = [20000, 10000, 3000, 2000, 1000, 500, 100]

# ============================================
# CACHÉ PARA REDUCIR PETICIONES A LA API
# ============================================

class CacheManager:
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.ttl = 60
    
    def get(self, key):
        if key in self.cache and key in self.timestamps:
            if (datetime.now() - self.timestamps[key]).seconds < self.ttl:
                return self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def clear(self):
        self.cache.clear()
        self.timestamps.clear()

if "cache_manager" not in st.session_state:
    st.session_state.cache_manager = CacheManager()

# ============================================
# CONFIGURACIÓN DE ESTILO
# ============================================

def aplicar_estilo():
    st.markdown("""
    <style>
        .card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }
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
        .main-title {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .planilla-separacion {
            background-color: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
        }
        .planilla-separacion h3 {
            color: #495057;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
        }
        .planilla-separacion .dependencia-item {
            background-color: white;
            border-radius: 5px;
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid #667eea;
        }
        .coincide {
            color: #28a745;
            font-weight: bold;
        }
        .no-coincide {
            color: #dc3545;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)

def conectar_gsheets():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            return client.open_by_key(SHEET_ID)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e

def limpiar_numero(valor):
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    
    if isinstance(valor, str):
        valor_str = valor.strip()
        if not valor_str:
            return 0
        
        valor_str = valor_str.replace("$", "").replace("$ ", "").replace(" ", "").strip()
        
        if not valor_str:
            return 0
        
        try:
            if "," in valor_str and "." in valor_str:
                if valor_str.rfind(",") > valor_str.rfind("."):
                    valor_str = valor_str.replace(".", "").replace(",", ".")
                else:
                    valor_str = valor_str.replace(",", "")
            elif "," in valor_str:
                partes = valor_str.split(",")
                if len(partes) == 2 and len(partes[1]) <= 2:
                    valor_str = valor_str.replace(",", ".")
                else:
                    valor_str = valor_str.replace(",", "")
            elif "." in valor_str:
                partes = valor_str.split(".")
                if len(partes) == 2 and len(partes[1]) <= 2:
                    pass
                else:
                    valor_str = valor_str.replace(".", "")
            
            if "." in valor_str:
                return int(float(valor_str))
            else:
                return int(valor_str)
                
        except (ValueError, TypeError):
            try:
                numeros = re.findall(r'\d+', valor_str)
                if numeros:
                    return int(''.join(numeros))
            except:
                pass
            return 0
    
    try:
        return int(float(valor))
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

@st.cache_data(ttl=60)
def obtener_dependencias_cached(anio, mes):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("dependencias")
        datos = ws.get_all_records()
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

def obtener_dependencias(anio=None, mes=None):
    if anio is None or mes is None:
        hoy = date.today()
        anio = hoy.year
        mes = hoy.month
    return obtener_dependencias_cached(anio, mes)

@st.cache_data(ttl=30)
def obtener_stock_cached():
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

def obtener_stock_actual():
    return obtener_stock_cached()

@st.cache_data(ttl=60)
def obtener_detalle_entregas_cached():
    try:
        sheet = conectar_gsheets()
        try:
            detalle_ws = sheet.worksheet("detalle_entregas")
            datos = detalle_ws.get_all_records()
            
            if datos and len(datos) > 0:
                columnas_numericas = ["cuota_objetivo", "total_entregado"]
                for d in DENOMINACIONES:
                    columnas_numericas.append(f"vale_{d}")
                
                for fila in datos:
                    for col in columnas_numericas:
                        if col in fila and fila[col] is not None:
                            try:
                                if isinstance(fila[col], str):
                                    fila[col] = limpiar_numero(fila[col])
                                else:
                                    fila[col] = float(fila[col])
                            except:
                                fila[col] = 0
            
            return datos
        except Exception as e:
            st.warning(f"No se pudo acceder a la hoja detalle_entregas: {e}")
            return []
    except Exception as e:
        st.warning(f"Error al leer detalle de entregas: {e}")
        return []

def obtener_detalle_entregas():
    return obtener_detalle_entregas_cached()

def actualizar_stock(stock_nuevo):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        
        for denom, cantidad in stock_nuevo.items():
            if cantidad < 0:
                st.error(f"Error: Stock negativo para ${denom}: {cantidad}")
                return False
        
        for denom, cantidad in stock_nuevo.items():
            cell = ws.find(str(denom))
            if cell:
                ws.update_cell(cell.row, 2, cantidad)
                time.sleep(0.5)
        
        st.cache_data.clear()
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
            encabezados = ["fecha", "dependencia_id", "dependencia_nombre", "cuota_objetivo", "total_entregado", "tipo"]
            for d in DENOMINACIONES:
                encabezados.append(f"vale_{d}")
            detalle_ws.append_row(encabezados)
        
        for ofi in reparto:
            # Calcular el total a partir de los vales
            total_calculado = 0
            for i, denom in enumerate(DENOMINACIONES):
                total_calculado += ofi["vales"][i] * denom
            
            nueva_fila = [
                str(fecha), 
                ofi.get("id", 0), 
                ofi["nombre"], 
                float(ofi.get("cuota_objetivo", 0)), 
                float(total_calculado),
                tipo
            ]
            for j, denom in enumerate(DENOMINACIONES):
                nueva_fila.append(int(ofi["vales"][j]))
            detalle_ws.append_row(nueva_fila)
            time.sleep(0.3)
        
        st.cache_data.clear()
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
            "total": 0,
            "diferencia": 0,
            "porcentaje_cumplido": 0
        })
    
    stock = stock_actual.copy()
    
    total_cuotas = sum(ofi["cuota_objetivo"] for ofi in reparto)
    total_stock = sum(denom * cantidad for denom, cantidad in stock.items())
    factor_ajuste = min(1.0, total_stock / total_cuotas) if total_cuotas > 0 else 0
    
    def distribuir_denominacion(valor_vale, cantidad_disponible, deudores):
        if cantidad_disponible <= 0 or not deudores:
            return
        
        necesidades = []
        for ofi in deudores:
            deuda = ofi["cuota_objetivo"] * factor_ajuste - ofi["total"]
            if deuda > 0:
                vales_necesarios = int(deuda // valor_vale)
                if vales_necesarios > 0:
                    necesidades.append({
                        "ofi": ofi,
                        "vales_necesarios": vales_necesarios,
                        "deuda": deuda
                    })
        
        if not necesidades:
            return
        
        necesidades.sort(key=lambda x: x["deuda"], reverse=True)
        
        vales_restantes = cantidad_disponible
        for necesidad in necesidades:
            if vales_restantes <= 0:
                break
            
            vales_a_dar = min(necesidad["vales_necesarios"], vales_restantes)
            if vales_a_dar > 0:
                ofi = necesidad["ofi"]
                idx = DENOMINACIONES.index(valor_vale)
                ofi["vales"][idx] += vales_a_dar
                ofi["total"] += vales_a_dar * valor_vale
                vales_restantes -= vales_a_dar
        
        stock[valor_vale] = vales_restantes
    
    for valor_vale in DENOMINACIONES:
        cantidad_disponible = stock[valor_vale]
        if cantidad_disponible <= 0:
            continue
        
        deudores = [
            ofi for ofi in reparto 
            if ofi["total"] < ofi["cuota_objetivo"] * factor_ajuste
        ]
        
        if not deudores:
            break
        
        distribuir_denominacion(valor_vale, cantidad_disponible, deudores)
    
    for valor_vale in reversed(DENOMINACIONES):
        cantidad_disponible = stock[valor_vale]
        if cantidad_disponible <= 0:
            continue
        
        deudores = [
            ofi for ofi in reparto 
            if ofi["total"] < ofi["cuota_objetivo"] * factor_ajuste
        ]
        
        if not deudores:
            break
        
        distribuir_denominacion(valor_vale, cantidad_disponible, deudores)
    
    # Recalcular totales a partir de los vales
    for ofi in reparto:
        total_calculado = 0
        for i, denom in enumerate(DENOMINACIONES):
            total_calculado += ofi["vales"][i] * denom
        
        ofi["total"] = total_calculado
        ofi["diferencia"] = ofi["cuota_objetivo"] - ofi["total"]
        ofi["porcentaje_cumplido"] = (ofi["total"] / ofi["cuota_objetivo"] * 100) if ofi["cuota_objetivo"] > 0 else 0
    
    return reparto, stock

def validar_distribucion(reparto, stock_inicial, stock_final):
    for denom, cantidad in stock_final.items():
        if cantidad < 0:
            return False, f"Stock negativo para ${denom}: {cantidad}"
    
    total_entregado = sum(ofi["total"] for ofi in reparto)
    total_stock_inicial = sum(denom * cantidad for denom, cantidad in stock_inicial.items())
    total_stock_final = sum(denom * cantidad for denom, cantidad in stock_final.items())
    
    tolerancia = 100
    
    if total_entregado > total_stock_inicial + tolerancia:
        return False, f"Total entregado excede stock inicial"
    
    if abs((total_stock_inicial - total_stock_final) - total_entregado) > tolerancia:
        return False, f"Diferencia de stock no coincide con entregado"
    
    for ofi in reparto:
        if ofi["total"] <= 0 and ofi["cuota_objetivo"] > 0:
            return False, f"La dependencia {ofi['nombre']} no recibió vales"
    
    return True, "Distribución válida"

def registrar_historial(fecha, reparto, tipo, es_ingreso=False, vales_ingresados=None):
    try:
        sheet = conectar_gsheets()
        try:
            historial_ws = sheet.worksheet("entregas_semanales")
        except:
            historial_ws = sheet.add_worksheet(title="entregas_semanales", rows="1000", cols="20")
            historial_ws.append_row(["fecha", "dependencia_id", "vale_100", "vale_500", "vale_1000", "vale_2000", "vale_3000", "vale_10000", "vale_20000", "descripcion"])
        
        if es_ingreso and vales_ingresados:
            nueva_fila = [
                str(fecha), 
                0, 
                vales_ingresados.get(100, 0), 
                vales_ingresados.get(500, 0), 
                vales_ingresados.get(1000, 0), 
                vales_ingresados.get(2000, 0), 
                vales_ingresados.get(3000, 0), 
                vales_ingresados.get(10000, 0), 
                vales_ingresados.get(20000, 0), 
                f"INGRESO - {tipo}"
            ]
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
            nueva_fila = [
                str(fecha), 
                0, 
                totales[0], 
                totales[1], 
                totales[2], 
                totales[3], 
                totales[4], 
                totales[5], 
                totales[6], 
                f"DISTRIBUCION - {tipo}"
            ]
        historial_ws.append_row(nueva_fila)
        time.sleep(0.3)
        return True
    except Exception as e:
        st.error(f"Error al registrar historial: {e}")
        return False

# ============================================
# FUNCIONES DE MEJORAS
# ============================================

def mostrar_dashboard(dependencias, stock, total_caja, miercoles):
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
    if not reparto:
        st.info("No hay datos para mostrar gráficos")
        return
    
    try:
        import plotly.express as px
        
        if not all(isinstance(ofi, dict) and "nombre" in ofi and "total" in ofi and "cuota_objetivo" in ofi for ofi in reparto):
            st.warning("Los datos de distribución no tienen el formato esperado")
            return
        
        st.subheader("📈 Gráfico de Distribución")
        
        df_grafico = pd.DataFrame([
            {
                "Dependencia": str(ofi.get("nombre", "Sin nombre")),
                "Total Entregado": float(ofi.get("total", 0)),
                "Cuota": float(ofi.get("cuota_objetivo", 0))
            }
            for ofi in reparto
        ])
        
        if df_grafico.empty:
            st.info("No hay datos para mostrar en el gráfico")
            return
        
        fig = px.bar(
            df_grafico, 
            x="Dependencia", 
            y=["Total Entregado", "Cuota"],
            title="Distribución por Dependencia",
            barmode="group",
            color_discrete_sequence=["#667eea", "#38ef7d"],
            text_auto=True
        )
        
        fig.update_layout(
            xaxis_tickangle=-45,
            yaxis_title="Monto ($)",
            legend_title="Métrica"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except ImportError:
        st.info("📊 Instala plotly para ver gráficos: pip install plotly")
    except Exception as e:
        st.error(f"Error al generar gráfico: {e}")

def descargar_reporte_csv(reparto, fecha):
    if reparto:
        try:
            df_reporte = []
            for ofi in reparto:
                fila = {
                    "Dependencia": ofi.get("nombre", ""),
                    "Cuota_Objetivo": ofi.get("cuota_objetivo", 0),
                    "Total_Entregado": ofi.get("total", 0),
                    "Porcentaje_Cumplido": ofi.get("porcentaje_cumplido", 0)
                }
                for i, denom in enumerate(DENOMINACIONES):
                    if "vales" in ofi and len(ofi["vales"]) > i:
                        fila[f"Vale_{denom}"] = ofi["vales"][i]
                    else:
                        fila[f"Vale_{denom}"] = 0
                df_reporte.append(fila)
            
            df = pd.DataFrame(df_reporte)
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            b64 = base64.b64encode(csv).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="distribucion_{fecha}.csv">⬇️ Descargar Reporte CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error al generar reporte CSV: {e}")

def simular_notificacion(mensaje):
    st.success(f"📧 {mensaje}")

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
    
    # Para una fecha específica, mostrar los datos tal como están
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
    
    # Calcular el total a partir de los vales para CADA registro
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

def forzar_actualizacion():
    st.cache_data.clear()
    if "cache_manager" in st.session_state:
        st.session_state.cache_manager.clear()
    st.rerun()

# ============================================
# INTERFAZ PRINCIPAL
# ============================================

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
    
    if st.sidebar.button("🔄 Forzar actualización de datos"):
        forzar_actualizacion()
        st.success("✅ Datos actualizados")
    
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
            .planilla-separacion {
                background-color: #16213e;
                color: #ffffff;
                border-color: #2d2d2d;
            }
            .planilla-separacion h3 {
                color: #ffffff;
                border-bottom-color: #2d2d2d;
            }
            .planilla-separacion .dependencia-item {
                background-color: #1a1a2e;
                color: #ffffff;
            }
        </style>
        """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"📆 Mostrando datos de {meses[mes_seleccionado-1]} {año_seleccionado}")
    
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
                    forzar_actualizacion()
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
                        forzar_actualizacion()
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
                tabla_deps.append({
                    "ID": dep["id"], 
                    "Dependencia": dep["nombre"], 
                    "Monto Mensual": f"${dep['monto_mensual']:,.0f}", 
                    "Monto Semanal": f"${monto_semanal:,.0f}"
                })
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
                    
                    mostrar_graficos(reparto)
                    
                    datos_tabla = []
                    for ofi in reparto:
                        cuota = ofi['cuota_objetivo']
                        total = ofi['total']
                        diferencia = cuota - total
                        porcentaje = ofi.get('porcentaje_cumplido', 0)
                        
                        if porcentaje >= 100:
                            color = "🟢"
                        elif porcentaje >= 80:
                            color = "🟡"
                        else:
                            color = "🔴"
                        
                        datos_tabla.append({
                            "Dependencia": ofi["nombre"],
                            "Cuota": f"${cuota:,.0f}",
                            "Entregado": f"${total:,.0f}",
                            "Diferencia": f"${diferencia:,.0f}",
                            "% Cumplido": f"{porcentaje:.1f}% {color}",
                            "$20k": ofi["vales"][0],
                            "$10k": ofi["vales"][1],
                            "$3k": ofi["vales"][2],
                            "$2k": ofi["vales"][3],
                            "$1k": ofi["vales"][4],
                            "$500": ofi["vales"][5],
                            "$100": ofi["vales"][6]
                        })
                    st.dataframe(
                        pd.DataFrame(datos_tabla), 
                        use_container_width=True,
                        column_config={
                            "% Cumplido": st.column_config.TextColumn(
                                "% Cumplido",
                                help="Porcentaje de la cuota cumplido"
                            )
                        }
                    )
                    
                    st.subheader("📊 Estadísticas de Cumplimiento")
                    cumplidos = sum(1 for ofi in reparto if ofi["total"] >= ofi["cuota_objetivo"])
                    total_deps = len(reparto)
                    porcentaje_cumplidos = (cumplidos / total_deps * 100) if total_deps > 0 else 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("✅ Dependencias cumplidas", f"{cumplidos}/{total_deps}")
                    with col2:
                        st.metric("📊 Porcentaje de cumplimiento", f"{porcentaje_cumplidos:.1f}%")
                    with col3:
                        st.metric("💰 Total entregado", f"${sum(ofi['total'] for ofi in reparto):,.0f}")
                    
                    descargar_reporte_csv(reparto, fecha_dist.strftime("%Y-%m-%d"))
                    
                    st.session_state.reparto = reparto
                    st.session_state.stock_nuevo = stock_nuevo
                    st.session_state.fecha_dist = fecha_dist
            
            if 'reparto' in st.session_state:
                with st.container():
                    st.markdown("---")
                    st.subheader("📋 Confirmar Distribución")
                    
                    es_valido, mensaje = validar_distribucion(
                        st.session_state.reparto,
                        stock,
                        st.session_state.stock_nuevo
                    )
                    
                    if es_valido:
                        st.success(f"✅ {mensaje}")
                    else:
                        st.error(f"❌ {mensaje}")
                        st.warning("⚠️ Revisa la distribución antes de guardar")
                    
                    total_entregado = sum(ofi["total"] for ofi in st.session_state.reparto)
                    total_cuotas = sum(ofi["cuota_objetivo"] for ofi in st.session_state.reparto)
                    total_diferencia = total_cuotas - total_entregado
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total a entregar", f"${total_entregado:,.0f}")
                    with col2:
                        st.metric("Total cuotas", f"${total_cuotas:,.0f}")
                    with col3:
                        st.metric("Diferencia", f"${total_diferencia:,.0f}")
                    with col4:
                        st.metric("Stock restante", f"${calcular_total_caja(st.session_state.stock_nuevo):,.0f}")
                    
                    st.subheader("📊 Resumen de Vales Utilizados")
                    vales_usados = {denom: 0 for denom in DENOMINACIONES}
                    for ofi in st.session_state.reparto:
                        for i, denom in enumerate(DENOMINACIONES):
                            vales_usados[denom] += ofi["vales"][i]
                    
                    vales_df = pd.DataFrame([
                        {
                            "Denominación": f"${d:,.0f}",
                            "Usados": vales_usados[d],
                            "Stock Inicial": stock.get(d, 0),
                            "Stock Final": st.session_state.stock_nuevo.get(d, 0)
                        }
                        for d in DENOMINACIONES
                    ])
                    st.dataframe(vales_df, use_container_width=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("❌ Cancelar", use_container_width=True):
                            del st.session_state.reparto
                            del st.session_state.stock_nuevo
                            del st.session_state.fecha_dist
                            st.rerun()
                    with col2:
                        if st.button("✅ Confirmar y Guardar", type="primary", use_container_width=True):
                            if actualizar_stock(st.session_state.stock_nuevo):
                                registrar_historial(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                                registrar_entrega_detallada(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                                st.success("🎉 Distribución guardada exitosamente")
                                simular_notificacion(f"Distribución del {st.session_state.fecha_dist.strftime('%d/%m/%Y')} guardada")
                                del st.session_state.reparto
                                del st.session_state.stock_nuevo
                                del st.session_state.fecha_dist
                                forzar_actualizacion()
                            else:
                                st.error("❌ Error al guardar la distribución")
    
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
                reparto_manual.append({
                    "id": dep["id"], 
                    "nombre": dep["nombre"], 
                    "cuota_objetivo": cuota, 
                    "vales": vales_asignados, 
                    "total": total_asignado
                })
            
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
                forzar_actualizacion()
    
    # ========== TAB 5: STOCK ACTUAL ==========
    with tab5:
        st.header("💰 Stock Actual de Vales")
        if st.button("🔄 Refrescar stock"):
            forzar_actualizacion()
        stock = obtener_stock_actual()
        total_caja = calcular_total_caja(stock)
        stock_display = pd.DataFrame([
            {
                "Denominación": f"${d:,.0f}", 
                "Cantidad": stock.get(d, 0), 
                "Total": f"${d * stock.get(d, 0):,.0f}"
            } 
            for d in DENOMINACIONES
        ])
        st.dataframe(stock_display, use_container_width=True)
        st.metric("💵 Total en caja", f"${total_caja:,.0f}")
    
    # ========== TAB 6: HISTORIAL ==========
    with tab6:
        mostrar_historial_detallado()
