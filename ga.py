"""
Algoritmo genetico para la reposicion de efectivo en cajeros.

Representacion
--------------
Un individuo (cromosoma) es una lista de N genes, uno por cajero.
Cada gen es un par de indices:

    (i_monto, i_frecuencia)

donde i_monto apunta a la rejilla de montos validos de ESE cajero
(cada cajero tiene su propia rejilla porque su capacidad es distinta)
y i_frecuencia apunta a la lista FRECUENCIAS.

Trabajar con indices y no con los valores directos garantiza que
cualquier cromosoma, incluso despues de mutar, sigue siendo factible:
nunca se carga mas de la capacidad del dispensador.

Operadores
----------
seleccion : torneo de tamano k
cruce     : uniforme por gen (cada cajero se hereda de un padre u otro)
mutacion  : con prob. p_mut, un gen cambia de monto y/o frecuencia
            dando un paso corto en la rejilla (mutacion local)
elitismo  : los E mejores pasan intactos a la siguiente generacion

Todo con la biblioteca estandar: random y math.
"""

import random

from modelo import FRECUENCIAS, costo_plan, montos_posibles


class AlgoritmoGenetico:

    def __init__(self, atms, tam_poblacion=120, generaciones=300,
                 p_cruce=0.90, p_mutacion=0.06, torneo=3, elite=2,
                 semilla=7):
        self.atms = atms
        self.n = len(atms)
        self.tam_poblacion = tam_poblacion
        self.generaciones = generaciones
        self.p_cruce = p_cruce
        self.p_mutacion = p_mutacion
        self.torneo = torneo
        self.elite = elite
        self.rnd = random.Random(semilla)

        # Rejilla de montos de cada cajero (se calcula una sola vez)
        self.rejillas = [montos_posibles(a) for a in atms]

        self.historial = []   # (generacion, mejor, promedio)

    # -----------------------------------------------------------
    # Traduccion cromosoma <-> plan
    # -----------------------------------------------------------
    def decodificar(self, cromosoma):
        return [
            (self.rejillas[i][gm], FRECUENCIAS[gf])
            for i, (gm, gf) in enumerate(cromosoma)
        ]

    def evaluar(self, cromosoma):
        return costo_plan(self.atms, self.decodificar(cromosoma))

    # -----------------------------------------------------------
    # Poblacion inicial
    # -----------------------------------------------------------
    def individuo_aleatorio(self):
        return [
            (self.rnd.randrange(len(self.rejillas[i])),
             self.rnd.randrange(len(FRECUENCIAS)))
            for i in range(self.n)
        ]

    def poblacion_inicial(self):
        return [self.individuo_aleatorio() for _ in range(self.tam_poblacion)]

    # -----------------------------------------------------------
    # Operadores
    # -----------------------------------------------------------
    def seleccion_torneo(self, poblacion, costos):
        """Toma k individuos al azar y devuelve el de menor costo.

        El torneo permite que soluciones mediocres ganen de vez en
        cuando, lo que mantiene diversidad. Con k grande la presion
        selectiva sube y el GA converge mas rapido, pero se arriesga a
        quedarse en un optimo local.
        """
        mejor = None
        mejor_costo = float("inf")
        for _ in range(self.torneo):
            j = self.rnd.randrange(len(poblacion))
            if costos[j] < mejor_costo:
                mejor, mejor_costo = poblacion[j], costos[j]
        return mejor

    def cruce_uniforme(self, padre_a, padre_b):
        """Cada cajero se hereda de un padre o del otro, al azar.

        Es apropiado aqui porque los genes son casi independientes: la
        decision del ATM-007 no depende del ATM-032. Un cruce de un
        punto tendria sesgo posicional sin ninguna razon de negocio.
        """
        if self.rnd.random() > self.p_cruce:
            return list(padre_a), list(padre_b)
        h1, h2 = [], []
        for g in range(self.n):
            if self.rnd.random() < 0.5:
                h1.append(padre_a[g])
                h2.append(padre_b[g])
            else:
                h1.append(padre_b[g])
                h2.append(padre_a[g])
        return h1, h2

    def mutar(self, cromosoma):
        """Mutacion local: mueve el gen un paso en la rejilla.

        Un salto totalmente aleatorio destruiria demasiado la solucion
        en etapas avanzadas. El paso corto funciona como una busqueda
        local dentro del ciclo evolutivo.
        """
        nuevo = list(cromosoma)
        for i in range(self.n):
            if self.rnd.random() >= self.p_mutacion:
                continue
            gm, gf = nuevo[i]
            if self.rnd.random() < 0.5:
                paso = self.rnd.choice([-2, -1, 1, 2])
                gm = min(max(gm + paso, 0), len(self.rejillas[i]) - 1)
            else:
                paso = self.rnd.choice([-1, 1])
                gf = min(max(gf + paso, 0), len(FRECUENCIAS) - 1)
            nuevo[i] = (gm, gf)
        return nuevo

    # -----------------------------------------------------------
    # Ciclo evolutivo
    # -----------------------------------------------------------
    def ejecutar(self, verbose=True):
        poblacion = self.poblacion_inicial()
        costos = [self.evaluar(ind) for ind in poblacion]

        mejor = min(range(len(poblacion)), key=lambda i: costos[i])
        mejor_ind, mejor_costo = list(poblacion[mejor]), costos[mejor]

        for gen in range(1, self.generaciones + 1):
            orden = sorted(range(len(poblacion)), key=lambda i: costos[i])
            nueva = [list(poblacion[i]) for i in orden[:self.elite]]

            while len(nueva) < self.tam_poblacion:
                p1 = self.seleccion_torneo(poblacion, costos)
                p2 = self.seleccion_torneo(poblacion, costos)
                h1, h2 = self.cruce_uniforme(p1, p2)
                nueva.append(self.mutar(h1))
                if len(nueva) < self.tam_poblacion:
                    nueva.append(self.mutar(h2))

            poblacion = nueva
            costos = [self.evaluar(ind) for ind in poblacion]

            i_mejor = min(range(len(poblacion)), key=lambda i: costos[i])
            if costos[i_mejor] < mejor_costo:
                mejor_ind = list(poblacion[i_mejor])
                mejor_costo = costos[i_mejor]

            promedio = sum(costos) / len(costos)
            self.historial.append((gen, mejor_costo, promedio))

            if verbose and (gen % 25 == 0 or gen == 1):
                print("gen {:>4} | mejor {:>16,.0f} | promedio {:>16,.0f}"
                      .format(gen, mejor_costo, promedio))

        return self.decodificar(mejor_ind), mejor_costo
