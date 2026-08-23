# Guía base de UI/UX

## Propósito y alcance

Esta guía establece un lenguaje común para las vistas actuales y los módulos futuros de pksControl-cpanel. Es una base de diseño y contenido; no modifica por sí misma templates, lógica ni estilos. Las decisiones deben conservar los permisos existentes y ser claras para una persona que captura, consulta o importa información.

## Patrones reutilizables actuales

Los templates ya comparten estos patrones definidos en `base.html`:

- `page-header`: título, contexto breve y acciones de la página.
- `page-actions`: grupo de botones y enlaces relacionados.
- `card`, `card-grid` y `quick-card`: agrupación visual de contenido y resúmenes.
- `form-grid`, `field-error` y `errorlist`: formularios y validaciones por campo.
- `table-wrap`, `data-table` y `pagination`: tablas responsivas y navegación por páginas.
- `alert`, `badge`, `badge-ok`, `badge-warning` y `badge-error`: mensajes y estados.
- `muted`: ayuda secundaria, nombres de archivo y aclaraciones.

En nuevas vistas se deben reutilizar estas clases antes de crear variantes. Las acciones condicionadas por permisos deben conservar el patrón actual: ocultar la acción no autorizada y proteger también la vista en servidor.

## 1. Páginas de listado

Estructura recomendada:

1. `page-header` con título, descripción de una línea y acciones principales.
2. `card` de filtros, usando `form method="get"`.
3. `card` con `table-wrap` y `data-table`.
4. Estado vacío o sin resultados dentro de la tabla.
5. `pagination` conservando todos los filtros excepto `page`.

Ejemplo para números de parte: “Números de parte”, botón “Nuevo número de parte”, filtros “Buscar”, “Modelo”, “Fracción” y “Estado”. El listado debe indicar claramente si muestra activos, inactivos o todos, y cada fila debe ofrecer “Ver detalle” y “Editar” solo cuando corresponda.

Ejemplo para conceptos: “Documentos de conceptos”, con estado visible (“Borrador”, “Confirmado”, “Cancelado”), folio, fecha, usuario y total. El estado debe usar una etiqueta consistente, no depender solo del color.

## 2. Formularios

- Usar un título orientado a la acción: “Nuevo número de parte” o “Editar número de parte”.
- Mantener etiquetas completas y consistentes: “Número de parte”, “Modelo”, “Descripción”, “Fracción”.
- Marcar requisitos en la etiqueta o ayuda; no depender únicamente de un asterisco.
- Mostrar el error junto al campo y un resumen superior para errores generales.
- Conservar los valores capturados cuando la validación falla.
- Separar “Guardar” como acción primaria y “Cancelar”/“Volver” como secundaria.
- No usar un botón genérico como “Enviar”.

Para un concepto, “Número de parte”, “Serie”, “Modelo”, “Descripción”, “Cantidad” y “Precio unitario” deben mantener el orden de captura habitual. Las acciones de búsqueda o sugerencia deben explicar qué datos precargarán y no reemplazar silenciosamente cantidad, precio o serie.

## 3. Importaciones CSV/XLSX

La pantalla debe decir siempre “CSV o XLSX” cuando ambos formatos estén soportados. Evitar textos heredados como “Importar CSV”. Usar “Seleccionar archivo” y “Generar preview” para la primera acción.

Para números de parte, documentar las columnas por posición: A `numero_parte` (obligatorio), B `modelo`, C `descripcion` (obligatorio), D `fraccion`. Aceptar encabezados, ignorar filas completamente vacías y explicar que una fila parcial sí se valida y puede producir error.

El flujo recomendado es: seleccionar archivo → generar preview → revisar resumen y errores → confirmar o cancelar → mostrar resultado y acciones posteriores. La confirmación debe ser una acción explícita y no ejecutarse al cargar el archivo.

## 4. Preview

El preview debe aparecer después del formulario y recibir foco o desplazamiento accesible cuando se genere. Puede usar un encabezado con el nombre del archivo, un `card-grid` de métricas y una tabla de muestra.

Para números de parte, mostrar como mínimo: filas válidas, registros que se crearían, registros que se actualizarían y errores. Ejemplo: “3 filas válidas · 2 nuevas · 1 actualización · 0 errores”. Indicar “Listo para confirmar” únicamente cuando no haya errores bloqueantes.

Para conceptos, mostrar filas totales, válidas, con sugerencia, duplicadas, incompletas y con error. Cada fila debe mostrar número de fila, datos relevantes, estado, mensaje y total cuando aplique.

## 5. Tablas de errores

- Encabezados mínimos: “Fila” y “Error” o “Mensaje”.
- Usar el número real de fila del archivo, incluyendo el encabezado cuando aplique.
- Escribir causa y corrección: “Fila 7: falta `numero_parte`” es preferible a “Dato inválido”.
- Mantener visibles los primeros errores y comunicar si existe un límite de muestra.
- No presentar una fila completamente vacía como error.
- Diferenciar error de fila, advertencia de estado y error general de sistema.

## 6. Mensajes de éxito y error

Los mensajes deben indicar qué ocurrió y qué puede hacer la persona después:

- Éxito: “Importación confirmada: 2 creados y 1 actualizado. Ver listado”.
- Éxito parcial: “Importación confirmada con 2 errores; revisa el detalle”.
- Error de validación: “Corrige los errores del preview antes de confirmar”.
- Error de formato: “Formato no soportado. Usa CSV o XLSX”.
- Error de sistema: “No se pudo completar la operación. Revisa el log o contacta soporte”.

Usar `alert-success` para éxito, `alert-error` para errores y `badge-*` para estados compactos. El mensaje no debe depender solo del color y debe ser legible por tecnologías de asistencia.

## 7. Botones y acciones

Cada pantalla debe tener una acción primaria identificable y acciones secundarias agrupadas. Preferir verbos específicos: “Generar preview”, “Confirmar importación”, “Cancelar”, “Guardar número de parte”, “Ver detalle”, “Activar” e “Inactivar”.

Después de crear o editar un número de parte, navegar al detalle guardado. Después de confirmar una importación, mostrar el resultado con enlaces a “Ver números de parte” y “Ver historial de cargas”. Después de cancelar, limpiar el preview y volver a la pantalla de importación con un mensaje claro.

Las acciones destructivas o irreversibles deben pedir confirmación cuando exista riesgo. Activar/inactivar debe indicar el estado resultante y no confundirse con eliminar.

## 8. Filtros

Los filtros deben tener etiquetas, valores conservados al paginar, botón “Buscar” y una acción “Limpiar filtros” cuando haya más de un criterio. Usar nombres de dominio comprensibles: “Estado: Activos”, “Inactivos” y “Todos”.

La búsqueda general puede cubrir número de parte, modelo, descripción y fracción; los filtros específicos deben combinarse de forma acumulativa. Informar el contexto del resultado: “12 números de parte encontrados” o “No hay resultados para los filtros actuales”.

## 9. Estados vacíos y sin resultados

Un listado vacío debe explicar por qué y ofrecer una siguiente acción:

- Sin registros: “Aún no hay números de parte. Crear el primero”.
- Sin coincidencias: “No hay resultados para estos filtros. Limpiar filtros”.
- Sin historial: “Todavía no hay cargas registradas”.
- Preview vacío: “El archivo no contiene filas válidas para importar”.

No confundir ausencia de datos con error del sistema. Si una acción no está disponible por permisos, no mostrar un botón que terminará en error; mantener una navegación segura de regreso.

## 10. Accesibilidad y navegación

Los títulos deben seguir una jerarquía (`h1` y `h2`), los botones deben describir su acción y los errores deben conservar foco o anunciarse de forma accesible. Tras generar un preview o detectar errores, mover el foco al encabezado de esa sección sin impedir que la persona vuelva al formulario.

En cambios futuros se recomienda usar un ancla o `id` estable para `preview`, `errores` y `resultado-importacion`, además de `role="alert"` para mensajes dinámicos. Las tablas deben conservar encabezados, contraste y lectura horizontal en pantallas pequeñas.

## 11. Checklist antes de publicar una vista

- ¿El título describe la tarea y los textos usan acentos?
- ¿La acción primaria es única, visible y específica?
- ¿Los permisos ocultan y protegen las acciones?
- ¿El estado vacío y el estado sin resultados tienen orientación?
- ¿Los filtros se conservan al paginar y pueden limpiarse?
- ¿La importación distingue formato, preview, confirmación y resultado?
- ¿Los errores incluyen fila, causa y corrección?
- ¿La navegación posterior permite continuar sin volver atrás manualmente?
- ¿Se validó teclado, foco, lector de pantalla y vista móvil?

## Fases propuestas

1. **Fase 1 — Textos/acciones:** corregir acentos, nombres de botones, mensajes y navegación posterior.
2. **Fase 2 — Importaciones/previews:** unificar CSV/XLSX, resumen, foco, confirmación y tabla de errores.
3. **Fase 3 — Listados/filtros:** normalizar filtros, estados vacíos, paginación y conteos.
4. **Fase 4 — Formularios:** etiquetas, ayudas, errores por campo, orden y acciones primarias/secundarias.
5. **Fase 5 — Componentes reutilizables:** extraer parciales consistentes para encabezados, alertas, estados, tablas y paginación.
