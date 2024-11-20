from flask import Flask, render_template, jsonify, request
import yfinance as yf
import pandas as pd
from datetime import datetime
import traceback
import numpy as np
from scipy import stats

app = Flask(__name__)

# Sugerencias de símbolos populares de la BMV
SIMBOLOS_SUGERIDOS = {
    'FEMSA': 'FEMSA.MX',
    'WALMEX': 'WALMEX.MX',
    'BIMBO': 'BIMBOA.MX',
    'TLEVISA': 'TLEVICPO.MX',
    'AMX': 'AMXL.MX',
    'CEMEX': 'CEMEXCPO.MX',
    'GFNORTE': 'GFNORTEO.MX',
    'GMXT': 'GMXT.MX',
    'ORBIA': 'ORBIA.MX',
    'ELEKTRA': 'ELEKTRA.MX'
}


def formatear_simbolo(simbolo, mercado=None):
    """
    Formatea el símbolo según el mercado especificado.
    """
    simbolo = simbolo.upper().strip()

    if simbolo in SIMBOLOS_SUGERIDOS:
        return SIMBOLOS_SUGERIDOS[simbolo]

    if not mercado:
        return simbolo

    sufijos_mercado = {
        'BMV': '.MX',
        'NYSE': '',
        'NASDAQ': '',
        'LON': '.L',
        'TSX': '.TO',
    }

    sufijo = sufijos_mercado.get(mercado.upper(), '')
    return f"{simbolo}{sufijo}"


def calcular_recomendacion(hist, info):
    """
    Calcula la recomendación de inversión basada en análisis técnico y fundamental.
    """
    rendimientos_diarios = hist['Close'].pct_change()
    volatilidad = rendimientos_diarios.std() * np.sqrt(252)  # Anualizada

    x = np.arange(len(hist['Close']))
    slope, _, r_value, _, _ = stats.linregress(x, hist['Close'])
    tendencia = slope > 0
    r_squared = r_value ** 2

    pe_ratio = info.get('forwardPE', 0)
    dividend_yield = info.get('dividendYield', 0) or 0

    score = 0
    razones = []

    if tendencia:
        score += 2
        razones.append("La acción muestra una tendencia alcista")

    if r_squared > 0.7:
        score += 1
        razones.append("La tendencia es consistente")

    if volatilidad < 0.3:
        score += 2
        razones.append("La volatilidad es moderada")

    if 10 < pe_ratio < 25:
        score += 1
        razones.append("El ratio P/E está en un rango saludable")

    if dividend_yield > 0.02:
        score += 1
        razones.append("Ofrece un dividendo atractivo")

    if score >= 5:
        recomendacion = "Comprar"
        nivel_riesgo = "Bajo"
        inversion_sugerida = "Se sugiere invertir hasta un 5% de tu portafolio"
    elif score >= 3:
        recomendacion = "Mantener"
        nivel_riesgo = "Moderado"
        inversion_sugerida = "Se sugiere invertir hasta un 3% de tu portafolio"
    else:
        recomendacion = "Esperar"
        nivel_riesgo = "Alto"
        inversion_sugerida = "No se recomienda invertir en este momento"

    return {
        "recomendacion": recomendacion,
        "nivel_riesgo": nivel_riesgo,
        "inversion_sugerida": inversion_sugerida,
        "razones": razones,
        "score": score
    }


def analizar_accion(simbolo, mercado=None):
    """
    Analiza una acción y retorna información detallada sobre ella.
    """
    try:
        simbolo_formateado = formatear_simbolo(simbolo, mercado)
        accion = yf.Ticker(simbolo_formateado)
        hist = accion.history(period="6mo")
        info = accion.info

        if hist.empty:
            return {
                "error": f"No se encontraron datos para el símbolo {simbolo_formateado}. Verifica que el símbolo y el mercado sean correctos."
            }

        precio_actual = hist['Close'][-1]
        precio_inicial = hist['Close'][0]
        rendimiento = ((precio_actual - precio_inicial) / precio_inicial) * 100

        nombre_empresa = info.get('longName', simbolo_formateado)
        descripcion = info.get('longBusinessSummary', 'Información no disponible')
        logo_url = info.get('logo_url', '')

        analisis = calcular_recomendacion(hist, info)

        return {
            "simbolo": simbolo_formateado,
            "nombre_empresa": nombre_empresa,
            "precio_actual": round(precio_actual, 2),
            "rendimiento_periodo": round(rendimiento, 2),
            "volumen_promedio": int(hist['Volume'].mean()),
            "precio_maximo": round(hist['High'].max(), 2),
            "precio_minimo": round(hist['Low'].min(), 2),
            "precios": hist['Close'].tolist(),
            "fechas": hist.index.strftime('%Y-%m-%d').tolist(),
            "descripcion": descripcion,
            "logo_url": logo_url,
            "recomendacion": analisis["recomendacion"],
            "nivel_riesgo": analisis["nivel_riesgo"],
            "inversion_sugerida": analisis["inversion_sugerida"],
            "razones_analisis": analisis["razones"]
        }
    except Exception:
        return {
            "error": "Error al analizar la acción. Verifica el símbolo y el mercado e intenta de nuevo."
        }


@app.route('/')
def home():
    """Ruta principal que muestra la interfaz de usuario."""
    return render_template('index.html', simbolos=SIMBOLOS_SUGERIDOS)


@app.route('/api/analizar')
def api_analizar():
    """API endpoint para analizar una acción."""
    simbolo = request.args.get('simbolo', '')
    mercado = request.args.get('mercado', None)

    if not simbolo:
        return jsonify({"error": "Por favor, proporciona un símbolo de acción."})

    resultado = analizar_accion(simbolo, mercado)
    return jsonify(resultado)


if __name__ == '__main__':
    app.run(debug=True)
