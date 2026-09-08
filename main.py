"""
Ejecuta el experimento completo:

    1. carga los datos de los cajeros
    2. evalua la politica de referencia (visitar cada 7 dias, cargar al 85%)
    3. corre el algoritmo genetico
    4. compara y escribe los resultados en resultados/

Uso:
    python3 generar_datos.py      (una sola vez)
    python3 main.py
"""

import csv
import os
import time

from ga import AlgoritmoGenetico
from modelo import (HORIZONTE_DIAS, cargar_atms, costo_atm, costo_plan,
                    desglose_plan, plan_baseline)

BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(BASE, "atms.csv")
RUTA_RESULTADOS = os.path.join(BASE, "resultados")


def moneda(x):
    return "{:>16,.0f}".format(x)


def imprimir_desglose(titulo, d):
    print("\n" + titulo)
    print("  efectivo inmovilizado {}".format(moneda(d["inmovilizado"])))
    print("  transporte de valores {}".format(moneda(d["transporte"])))
    print("  desabastecimiento     {}".format(moneda(d["desabasto"])))
    print("  " + "-" * 38)
    print("  COSTO TOTAL           {}".format(moneda(d["total"])))
    print("  visitas en el periodo {:>16,.0f}".format(d["visitas"]))
    print("  peor prob. desabasto  {:>15.1%}".format(d["peor_prob_desabasto"]))


def guardar_plan(atms, plan, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["atm_id", "zona", "capacidad", "demanda_media",
                    "monto_carga", "frecuencia_dias", "visitas_periodo",
                    "prob_desabasto", "costo_total"])
        for atm, (monto, frec) in zip(atms, plan):
            c = costo_atm(atm, monto, frec)
            w.writerow([
                atm["atm_id"], atm["zona"], int(atm["capacidad"]),
                int(atm["demanda_media"]), int(monto), frec,
                round(c["visitas"], 1), round(c["prob_desabasto"], 4),
                int(c["total"]),
            ])


def guardar_convergencia(historial, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["generacion", "mejor_costo", "costo_promedio"])
        for gen, mejor, prom in historial:
            w.writerow([gen, int(mejor), int(prom)])


def main():
    os.makedirs(RUTA_RESULTADOS, exist_ok=True)
    atms = cargar_atms(RUTA_DATOS)

    print("Red: {} cajeros | horizonte: {} dias".format(len(atms), HORIZONTE_DIAS))

    # --- politica de referencia ---
    base = plan_baseline(atms)
    costo_base = costo_plan(atms, base)
    imprimir_desglose("POLITICA ACTUAL (cada 7 dias, 85% de capacidad)",
                      desglose_plan(atms, base))

    # --- algoritmo genetico ---
    print("\nCorriendo algoritmo genetico...")
    t0 = time.time()
    ga = AlgoritmoGenetico(atms, tam_poblacion=120, generaciones=300, semilla=7)
    plan, costo = ga.ejecutar()
    segundos = time.time() - t0

    imprimir_desglose("PLAN ENCONTRADO POR EL GA", desglose_plan(atms, plan))

    ahorro = costo_base - costo
    print("\n" + "=" * 46)
    print("  ahorro en el periodo  {}".format(moneda(ahorro)))
    print("  mejora relativa       {:>15.1%}".format(ahorro / costo_base))
    print("  tiempo de computo     {:>13.1f} s".format(segundos))
    print("=" * 46)

    guardar_plan(atms, plan, os.path.join(RUTA_RESULTADOS, "plan_ga.csv"))
    guardar_plan(atms, base, os.path.join(RUTA_RESULTADOS, "plan_baseline.csv"))
    guardar_convergencia(ga.historial,
                         os.path.join(RUTA_RESULTADOS, "convergencia.csv"))
    print("\nResultados escritos en resultados/")


if __name__ == "__main__":
    main()
