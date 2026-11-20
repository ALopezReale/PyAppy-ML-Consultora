# Bitácora del ETL

Generada automáticamente por `notebooks/01_ETL.ipynb`.

| paso | filas_antes | filas_despues | filas_eliminadas | valores_afectados | motivo |
|---|---|---|---|---|---|
| Carga | 1.048.575 | 1.048.575 | 0 | 0 | CSV crudo de Kaggle. |
| Filas vacías | 1.048.575 | 584.524 | 464.051 | 464.051 | Filas sin ningún dato: relleno del export a Excel. |
| Columnas vacías | 584.524 | 584.524 | 0 | 5 | Columnas 100 % vacías: Unnamed: 21, Unnamed: 22, Unnamed: 23, Unnamed: 24, Unnamed: 25. |
| Nombres de columnas | 584.524 | 584.524 | 0 | 21 | Nombres en snake_case para evitar errores por espacios. |
| Texto y marcador \N | 584.524 | 584.524 | 0 | 346.855 | '\N' es el nulo de MySQL: se trata como faltante. Strip de espacios. |
| Tipos de datos | 584.524 | 584.524 | 0 | 5 | created_at y customer_since a fecha; item_id, customer_id y qty_ordered a entero. |
| Columnas redundantes | 584.524 | 584.524 | 0 | 8 | working_date = created_at; year/month/m_y/fy salen de la fecha; mv = price×qty; bi_status depende solo de status. sales_commission_code (81 % faltante) → bandera uso_codigo_comision. |
| Nulos en columnas clave | 584.524 | 584.474 | 50 | 50 | Sin customer_id, status o sku la transacción no se puede atribuir. |
| Categoría por sku | 584.474 | 584.474 | 0 | 2.134 | Categoría faltante imputada con la categoría más frecuente del mismo sku. |
| Categoría desconocida | 584.474 | 584.474 | 0 | 5.859 | Sin referencia en otro registro del sku → 'Desconocida'. |
| Duplicados exactos | 584.474 | 584.474 | 0 | 0 | Filas idénticas o item_id repetido. |
| Líneas repetidas (se conservan) | 584.474 | 584.474 | 0 | 194 | Idénticas salvo item_id, pero el grand_total del pedido las suma: son compras legítimas. |
| Productos de prueba | 584.474 | 582.701 | 1.773 | 1.773 | 25 SKUs de prueba internos (test-product, test bundle, Test Hazir, tcsconnect...): no son ventas reales. |
| Cuenta interna probable (marcada) | 582.701 | 582.701 | 0 | 1.172 | Filas de 53 clientes con ≥30% de compras de prueba: se conservan y el EDA decide. |
| Descuento negativo | 582.701 | 582.701 | 0 | 2 | Un descuento no puede ser negativo → 0. |
| Descuento > bruto (marcado) | 582.701 | 582.701 | 0 | 9.711 | El descuento supera price×qty: dato poco confiable a nivel línea. monto_linea se recorta a 0. |
| grand_total negativo (marcado) | 582.701 | 582.701 | 0 | 76 | Total de pedido < 0 (descuento mayor al precio): se marca, no se borra. |
| Precio cero (marcado) | 582.701 | 582.701 | 0 | 2.206 | Regalos o errores de carga: no cuentan como compra válida. |
| Cantidad atípica (marcada) | 582.701 | 582.701 | 0 | 42 | qty_ordered > 100: posibles compras mayoristas; decide el EDA. |
| Variables nuevas | 582.701 | 582.701 | 0 | 3 | monto_bruto = price×qty; monto_linea = max(bruto − descuento, 0) (grand_total es por pedido); anio_mes. |
| Compra válida (bandera) | 582.701 | 582.701 | 0 | 314.565 | status ∈ ['closed', 'cod', 'complete', 'exchange', 'paid', 'received'] y price > 0. |
