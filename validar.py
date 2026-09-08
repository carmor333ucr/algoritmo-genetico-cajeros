"""
Valida el modelo analitico contra una simulacion Monte Carlo.

La funcion objetivo usa una formula cerrada para el faltante esperado.
Eso es lo que hace viable evaluar cientos de miles de planes, pero
introduce dos supuestos que conviene poner a prueba:

  1. la demanda diaria es normal
  2. la demanda acumulada de f dias tambien lo es

Este script simula la operacion dia a dia y compara el costo simulado
con el costo que predice el modelo. Si la brecha es pequena, la
aproximacion es defendible.

Uso:
    python3 validar.py
"""

import os
import random

from modelo import (COSTO_EVENTO_DESABASTO, COSTO_POR_COLON_FALTANTE,
                    HORIZONTE_DIAS, TASA_DIARIA, cargar_atms, costo_atm)

BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(BASE, "atms.csv")

REPLICAS = 4000


def simular_atm(atm, monto, frecuencia, replicas=REPLICAS, semilla=99):
    """Simula ciclos de reposicion y devuelve el costo promedio por periodo.

    En cada ciclo:
      - se carga el cajero con `monto`
      - se consumen `frecuencia` dias de demanda aleatoria
      - si la demanda acumulada supera el monto, hay desabasto
    """
    rnd = random.Random(semilla)
    ciclos_por_periodo = HORIZONTE_DIAS / float(frecuencia)

    faltante_total = 0.0
    eventos = 0

    for _ in range(replicas):
        acumulado = 0.0
        for _ in range(frecuencia):
            d = rnd.gauss(atm["demanda_media"], atm["demanda_desv"])
            acumulado += max(0.0, d)   # la demanda no puede ser negativa
        if acumulado > monto:
            faltante_total += acumulado - monto
            eventos += 1

    faltante_medio = faltante_total / replicas
    p_falla = eventos / float(replicas)

    costo_desabasto = ciclos_por_periodo * (
        faltante_medio * COSTO_POR_COLON_FALTANTE
        + p_falla * COSTO_EVENTO_DESABASTO
    )
    costo_inmovilizado = (monto / 2.0) * TASA_DIARIA * HORIZONTE_DIAS
    costo_transporte = atm["costo_visita"] * ciclos_por_periodo

    return {
        "total": costo_inmovilizado + costo_transporte + costo_desabasto,
        "desabasto": costo_desabasto,
        "prob_desabasto": p_falla,
    }


def main():
    atms = cargar_atms(RUTA_DATOS)
    rnd = random.Random(123)
    muestra = rnd.sample(atms, 8)

    print("Validacion del modelo analitico contra Monte Carlo "
          "({} replicas por caso)\n".format(REPLICAS))
    print("{:<10} {:>4} {:>14} {:>14} {:>8} {:>8} {:>8}".format(
        "atm", "frec", "costo modelo", "costo simul.", "brecha",
        "p model", "p simul"))
    print("-" * 72)

    brechas = []
    for atm in muestra:
        frecuencia = rnd.choice([2, 3, 5, 7, 10])
        monto = min(atm["capacidad"],
                    atm["demanda_media"] * frecuencia * 1.15)
        monto = round(monto / 500_000) * 500_000

        analitico = costo_atm(atm, monto, frecuencia)
        simulado = simular_atm(atm, monto, frecuencia)

        brecha = (analitico["total"] - simulado["total"]) / simulado["total"]
        brechas.append(abs(brecha))

        print("{:<10} {:>4} {:>14,.0f} {:>14,.0f} {:>7.2%} {:>8.1%} {:>8.1%}"
              .format(atm["atm_id"], frecuencia, analitico["total"],
                      simulado["total"], brecha,
                      analitico["prob_desabasto"], simulado["prob_desabasto"]))

    print("-" * 72)
    print("brecha absoluta promedio: {:.2%}".format(
        sum(brechas) / len(brechas)))
    print("brecha absoluta maxima:   {:.2%}".format(max(brechas)))
    print("\nSi la brecha se mantiene por debajo de ~2%, la formula cerrada")
    print("es un sustituto razonable de la simulacion para guiar la busqueda.")


if __name__ == "__main__":
    main()
