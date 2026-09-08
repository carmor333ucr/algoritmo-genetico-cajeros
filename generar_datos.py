"""
Genera datos simulados de una red de cajeros automaticos.

Salida: atms.csv

Cada ATM tiene:
  - zona: urbana / periferica / rural  (afecta el costo de la visita)
  - capacidad: monto maximo que admite el dispensador (colones)
  - demanda_media: retiro promedio por dia (colones)
  - demanda_desv: desviacion estandar del retiro diario (colones)
  - costo_visita: costo de una visita del transporte de valores (colones)

Los numeros son inventados pero con ordenes de magnitud plausibles para
una red bancaria mediana. Semilla fija para que el experimento sea
reproducible.
"""

import csv
import os
import random

SEMILLA = 42
N_ATMS = 40

# (nombre, costo_visita, factor_demanda, prob)
ZONAS = [
    ("urbana", 45_000, 1.30, 0.45),
    ("periferica", 70_000, 1.00, 0.35),
    ("rural", 145_000, 0.65, 0.20),
]

DEMANDA_BASE = 1_400_000  # colones por dia, antes del factor de zona
CAPACIDADES = [10_000_000, 15_000_000, 20_000_000, 25_000_000]


def elegir_zona(rnd):
    r = rnd.random()
    acumulado = 0.0
    for zona in ZONAS:
        acumulado += zona[3]
        if r <= acumulado:
            return zona
    return ZONAS[-1]


def generar(n=N_ATMS, semilla=SEMILLA):
    rnd = random.Random(semilla)
    filas = []

    for i in range(1, n + 1):
        nombre, costo_visita, factor, _ = elegir_zona(rnd)

        # Demanda media: base * factor de zona * ruido individual del cajero
        ruido = rnd.uniform(0.55, 1.55)
        demanda_media = DEMANDA_BASE * factor * ruido

        # Variabilidad: los cajeros de alta demanda son proporcionalmente
        # mas estables (efecto de agregacion de muchos clientes).
        cv = rnd.uniform(0.22, 0.45)
        demanda_desv = demanda_media * cv

        # La capacidad instalada tiende a acompanar la demanda
        capacidad = min(
            CAPACIDADES[-1],
            max(
                CAPACIDADES[0],
                rnd.choice([c for c in CAPACIDADES if c >= demanda_media * 8.0]
                           or [CAPACIDADES[-1]]),
            ),
        )

        # Ruido en el costo de la visita (distancia, escolta, horario)
        costo = costo_visita * rnd.uniform(0.85, 1.20)

        filas.append({
            "atm_id": "ATM-{:03d}".format(i),
            "zona": nombre,
            "capacidad": int(round(capacidad, -5)),
            "demanda_media": int(round(demanda_media, -4)),
            "demanda_desv": int(round(demanda_desv, -4)),
            "costo_visita": int(round(costo, -3)),
        })

    return filas


def main():
    filas = generar()
    ruta = os.path.join(os.path.dirname(__file__), "atms.csv")
    ruta = os.path.abspath(ruta)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)

    demanda_total = sum(f["demanda_media"] for f in filas)
    print("Generados {} cajeros en {}".format(len(filas), ruta))
    print("Demanda agregada de la red: {:,.0f} colones/dia".format(demanda_total))


if __name__ == "__main__":
    main()
