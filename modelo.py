"""
Modelo de costos de la reposicion de efectivo en cajeros automaticos.

Un PLAN (la solucion que el algoritmo busca) asigna a cada cajero i:
    monto_i      : cuanto efectivo se carga en cada visita
    frecuencia_i : cada cuantos dias se visita el cajero

El costo total del plan en un horizonte de H dias es la suma de tres
componentes que se contradicen entre si:

  1. Costo de oportunidad del efectivo inmovilizado
     El saldo promedio del cajero durante un ciclo es aprox. monto/2.
     Ese dinero no genera rendimiento mientras esta dentro del ATM.
     -> baja si se cargan montos pequenos

  2. Costo del transporte de valores
     Cada visita cuesta (vehiculo, escolta, seguro).
     -> baja si se visita con poca frecuencia

  3. Costo de desabastecimiento
     Si la demanda del ciclo supera el monto cargado, el cajero se
     queda vacio: hay costo comercial y de reputacion.
     -> baja si se cargan montos grandes y se visita seguido

Minimizar 1 y 2 empuja hacia arriba el 3. Ese conflicto es lo que hace
que el problema no tenga una formula cerrada.

--------------------------------------------------------------------
Componente 3 en detalle
--------------------------------------------------------------------
La demanda acumulada de un ciclo de f dias se modela como normal:

    D ~ Normal(mu = f * demanda_media,  sigma = demanda_desv * sqrt(f))

(la desviacion crece con la raiz de f porque los dias se suponen
independientes)

El faltante esperado por ciclo es la "perdida parcial esperada" de la
normal, que tiene forma cerrada:

    z = (monto - mu) / sigma
    E[(D - monto)+] = sigma * ( phi(z) - z * (1 - Phi(z)) )

donde phi es la densidad normal estandar y Phi su acumulada.

Usar la formula cerrada en vez de simular Monte Carlo hace que la
evaluacion sea deterministica y ~1000x mas rapida, que es lo que
permite evaluar cientos de miles de planes. En validar.py se comprueba
contra una simulacion.
"""

import csv
import math

# ---------------------------------------------------------------
# Parametros del negocio (editables)
# ---------------------------------------------------------------
HORIZONTE_DIAS = 90

# Tasa de oportunidad anual del efectivo inmovilizado
TASA_ANUAL = 0.0650
TASA_DIARIA = TASA_ANUAL / 365.0

# Costo por cada colon que el cajero no pudo dispensar.
# Representa el costo comercial de mandar al cliente a otro lado.
COSTO_POR_COLON_FALTANTE = 0.035

# Costo fijo por evento de desabasto (llamadas, reclamos, visita de
# emergencia del transporte de valores)
COSTO_EVENTO_DESABASTO = 180_000

# Espacio de decision
FRECUENCIAS = list(range(1, 15))          # visitar cada 1 a 14 dias
PASO_MONTO = 500_000                      # los montos van de 500k en 500k
MONTO_MINIMO = 2_000_000


# ---------------------------------------------------------------
# Utilidades estadisticas (solo math, sin dependencias)
# ---------------------------------------------------------------
def _phi(z):
    """Densidad de la normal estandar."""
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def _Phi(z):
    """Acumulada de la normal estandar."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def faltante_esperado(monto, mu, sigma):
    """E[(D - monto)+] para D ~ Normal(mu, sigma)."""
    if sigma <= 0:
        return max(0.0, mu - monto)
    z = (monto - mu) / sigma
    return sigma * (_phi(z) - z * (1.0 - _Phi(z)))


def prob_desabasto(monto, mu, sigma):
    """P(D > monto)."""
    if sigma <= 0:
        return 1.0 if mu > monto else 0.0
    return 1.0 - _Phi((monto - mu) / sigma)


# ---------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------
def cargar_atms(ruta):
    atms = []
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            atms.append({
                "atm_id": fila["atm_id"],
                "zona": fila["zona"],
                "capacidad": float(fila["capacidad"]),
                "demanda_media": float(fila["demanda_media"]),
                "demanda_desv": float(fila["demanda_desv"]),
                "costo_visita": float(fila["costo_visita"]),
            })
    return atms


def montos_posibles(atm):
    """Rejilla de montos validos para un cajero, de PASO_MONTO en PASO_MONTO."""
    tope = int(atm["capacidad"] // PASO_MONTO)
    piso = max(1, MONTO_MINIMO // PASO_MONTO)
    return [k * PASO_MONTO for k in range(piso, tope + 1)]


# ---------------------------------------------------------------
# Funcion objetivo
# ---------------------------------------------------------------
def costo_atm(atm, monto, frecuencia, horizonte=HORIZONTE_DIAS):
    """Costo de un cajero bajo una politica (monto, frecuencia).

    Devuelve un diccionario con el desglose por componente.
    """
    ciclos = horizonte / float(frecuencia)

    # 1. efectivo inmovilizado
    saldo_promedio = monto / 2.0
    costo_inmovilizado = saldo_promedio * TASA_DIARIA * horizonte

    # 2. transporte de valores
    costo_transporte = atm["costo_visita"] * ciclos

    # 3. desabastecimiento
    mu = atm["demanda_media"] * frecuencia
    sigma = atm["demanda_desv"] * math.sqrt(frecuencia)
    faltante = faltante_esperado(monto, mu, sigma)
    p_falla = prob_desabasto(monto, mu, sigma)
    costo_desabasto = ciclos * (
        faltante * COSTO_POR_COLON_FALTANTE
        + p_falla * COSTO_EVENTO_DESABASTO
    )

    return {
        "inmovilizado": costo_inmovilizado,
        "transporte": costo_transporte,
        "desabasto": costo_desabasto,
        "total": costo_inmovilizado + costo_transporte + costo_desabasto,
        "prob_desabasto": p_falla,
        "visitas": ciclos,
    }


def costo_plan(atms, plan, horizonte=HORIZONTE_DIAS):
    """Costo total de la red. plan = lista de (monto, frecuencia) por ATM."""
    total = 0.0
    for atm, (monto, frecuencia) in zip(atms, plan):
        total += costo_atm(atm, monto, frecuencia, horizonte)["total"]
    return total


def desglose_plan(atms, plan, horizonte=HORIZONTE_DIAS):
    """Desglose agregado del plan, para reportar."""
    acum = {"inmovilizado": 0.0, "transporte": 0.0, "desabasto": 0.0,
            "total": 0.0, "visitas": 0.0}
    peor_prob = 0.0
    for atm, (monto, frecuencia) in zip(atms, plan):
        c = costo_atm(atm, monto, frecuencia, horizonte)
        for k in ("inmovilizado", "transporte", "desabasto", "total", "visitas"):
            acum[k] += c[k]
        peor_prob = max(peor_prob, c["prob_desabasto"])
    acum["peor_prob_desabasto"] = peor_prob
    return acum


# ---------------------------------------------------------------
# Politica de referencia (el "como se hace hoy")
# ---------------------------------------------------------------
def plan_baseline(atms, frecuencia_fija=7, llenado=0.85):
    """Regla simple: visitar todos los cajeros cada 7 dias y cargarlos
    al 85% de su capacidad. Es el punto de comparacion del GA."""
    plan = []
    for atm in atms:
        opciones = montos_posibles(atm)
        objetivo = atm["capacidad"] * llenado
        monto = min(opciones, key=lambda m: abs(m - objetivo))
        plan.append((monto, frecuencia_fija))
    return plan
