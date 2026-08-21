# La tarjeta de agente no se podía descubrir

**Rama:** `main`
**Fecha:** 2026-08-21

## Síntoma

La plataforma rechazaba la importación con "no es una tarjeta de agente A2A
válida (falta name o supportedInterfaces)", pese a que un `GET` con curl
devolvía el JSON completo con ambos campos presentes.

## Causa

Dos defectos distintos, ninguno en el contenido del documento:

1. **`HEAD` devolvía 405.** La ruta solo aceptaba `GET`. Un cliente que
   comprueba la existencia del documento antes de descargarlo interpretaba ese
   405 como que no existía.
2. **CORS cerrado.** El servicio no envía cabeceras CORS por diseño, porque la
   integración con `/responses` es servidor a servidor. Pero un documento de
   descubrimiento consultado desde un navegador queda bloqueado por el propio
   navegador, y el código que lo pide recibe un error genérico en lugar del
   JSON.

## Corrección

La ruta acepta `GET`, `HEAD` y `OPTIONS`, y responde con
`Access-Control-Allow-Origin: *`.

La apertura es **solo para esta ruta**. Un documento de descubrimiento que un
navegador no puede leer no descubre nada, y su contenido es público por
definición: declara qué es el agente y que espera un token Bearer, nunca cuál.
`/responses` conserva el CORS cerrado, porque ahí hay una credencial de por medio
y la integración no pasa por navegador.

## Verificación

Cinco pruebas nuevas cubren los tres métodos, la presencia de la cabecera CORS en
la tarjeta y, sobre todo, su **ausencia** en `/responses`: la apertura no debe
extenderse al resto del servicio por descuido.

145 pruebas en verde.
