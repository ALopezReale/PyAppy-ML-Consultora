# Decisiones del ETL

Responsable: Alam Flores · Sprint 1 · Código: `src/limpieza.py` · Ejecución: `notebooks/01_ETL.ipynb`.
La bitácora con los conteos exactos de cada paso se regenera en `docs/bitacora_etl.md` cada vez que se ejecuta el notebook.

## Resumen del impacto

| Métrica | Valor |
|---|---|
| Filas crudas | 1.048.575 |
| Filas vacías eliminadas (relleno del export) | 464.051 |
| Sin `customer_id`, `status` o `sku` | 50 |
| Productos de prueba internos | 1.773 |
| **Filas finales** | **582.701** (se elimina el 0,31 % de las reales) |
| Compras válidas (`es_compra_valida`) | 314.565 (54,0 %) |
| Clientes / SKUs con compra válida | 79.946 / 63.970 |

## Decisiones

| # | Decisión | Criterio | Impacto |
|---|---|---|---|
| 1 | Eliminar filas totalmente vacías | El CSV se exportó desde Excel (2²⁰ filas); son relleno | −464.051 filas |
| 2 | Eliminar 5 columnas `Unnamed` | 100 % vacías | −5 columnas |
| 3 | `\N` → nulo | Es el marcador de nulo de MySQL | 346.855 valores |
| 4 | Quitar columnas redundantes | Probado en el notebook (ver diccionario) | −7 columnas |
| 5 | `sales_commission_code` → bandera | 81 % faltante, el código no aporta. Los textos `NA` y `None` (7 celdas) cuentan como "sin código" | 1 columna reemplazada |
| 6 | Eliminar filas sin `customer_id`, `status` o `sku` | No se pueden atribuir a un cliente ni a un producto. Incluye 11 `Customer ID = "#N/A"` (error de Excel) | −50 filas |
| 7 | Imputar categoría por sku | Categoría más frecuente del mismo sku | 2.134 recuperadas |
| 8 | Categoría `"Desconocida"` | Sin referencia; la compra sigue sirviendo al recomendador | 5.859 filas (4.148 tras quitar los productos de prueba) |
| 9 | Conservar 194 líneas idénticas salvo `item_id` | El `grand_total` del pedido las incluye (89 % cuadra con ellas y 0,6 % sin ellas): son compras reales | 0 eliminadas |
| 9b | Eliminar productos de prueba | 25 SKUs internos de QA (`test-product`, `test bundle product`, `Test Hazir Product`, `test_tcsconnect`…), con precio mediano de 5 PKR. No son ventas, y un recomendador por popularidad podría recomendarlos. El patrón conserva productos reales con "test" (`SKMT_Blood Test`, la pelota `Test Star`, la marca `Vous Deteste`) | −1.773 filas (83 marcadas como válidas) |
| 9c | Marcar `cuenta_interna_probable` | Clientes con ≥ 30 % de compras de prueba: probable personal de la tienda. Se conservan sus compras reales | 53 clientes / 1.172 filas |
| 10 | Descuento negativo → 0 | Un descuento no puede ser negativo | 2 valores (el 3.º era un producto de prueba) |
| 11 | Marcar `grand_total` < 0, price = 0 y qty > 100 | Se marcan para que el EDA decida; no se borra información | 76 / 2.206 / 42 filas |
| 12 | Crear `monto_bruto` y `monto_linea` | `grand_total` es por pedido: sumarlo por ítem infla el ticket. `monto_linea` se recorta a 0 | 2 columnas nuevas |
| 12b | Marcar `descuento_inconsistente` | El descuento supera price × qty: se reparte de forma irregular entre las líneas (en 1.126 pedidos supera incluso el bruto del pedido). No se borra: la compra existió | 9.711 filas |
| 13 | Definir `es_compra_valida` | Estados concretados (complete, received, closed, paid, cod, exchange) y price > 0. Se excluyen canceladas, reembolsos, fraude y pendientes | 314.565 compras válidas |
| 14 | Guardar en Parquet | Conserva los tipos (fechas, enteros, booleanos) y pesa 16 MB contra 102 MB del CSV | `data/processed/transacciones_limpias.parquet` |

## Hallazgos para el EDA y el modelado

- **Período real:** jul-2016 a ago-2018 (la propuesta decía mar-2016). Hay picos en noviembre (11.11 / Black Friday) que afectan el split temporal.
- **Cold start:** el 64,6 % de los clientes con compra válida tiene un solo pedido.
- **Sparsity:** la matriz cliente × sku está vacía en un 99,995 %. Conviene evaluar recomendaciones a nivel categoría o un baseline de popularidad.
- **Ticket promedio:** calcularlo por pedido, con `grand_total` una vez por `increment_id`.
- **Volumen de compra:** usar `monto_bruto`. `discount_amount` y `monto_linea` no son confiables a nivel línea.
- **Cuentas internas:** excluir los clientes con `cuenta_interna_probable` al buscar clientes "top" o al segmentar.
- **Casos menores que se conservan:** 9 líneas con `increment_id` terminado en `-1` (pedidos re-emitidos) y 2 SKUs `ajrak` cargados en Women's y Men's Fashion.

## Cómo se verificó

- **Notebook:** se ejecuta de principio a fin con `jupyter nbconvert --execute`, sin errores ni warnings, y termina con 11 validaciones (`assert`) sobre el resultado.
- **Tests automáticos (`tests/test_limpieza.py`):** se corren con `pytest` desde la raíz del repo, en menos de un segundo.
  - *Casos borde:* un CSV sintético en el que cada fila es un caso raro a propósito (espacios, `\N`, `#N/A`, fechas mes/día, descuento mayor al precio, producto de prueba, producto real con "test" en el nombre…).
  - *Integridad del dataset real:* se saltea si no existe el parquet (`pytest -m "not datos"` corre solo los casos borde).
  - Se comprobó que los tests detectan los bugs: al reintroducir el `monto_linea` negativo o no borrar los productos de prueba, fallan.
- **Auditoría independiente (una sola vez, durante el sprint):** se releyó el CSV como texto, se recalculó cada columna sin usar `src/limpieza.py` y se comparó fila a fila con el parquet. Todos los controles coincidieron, y dos corridas del pipeline dan un resultado idéntico.

## Limitaciones conocidas

- 55 pedidos perdieron alguna línea en la limpieza (productos de prueba o filas sin clave), así que su `grand_total` todavía las incluye. Solo 14 tienen compras válidas: el efecto en el ticket promedio es despreciable.
