# EscoliGest - MVP local (Django + PostgreSQL en Docker)

Levanta el backend y Postgres con Docker Compose.

Pasos:
1. En la carpeta del proyecto (donde está docker-compose.yml) ejecutar:
   docker compose up --build

2. Crear superuser (en otra terminal):
   docker compose exec backend python manage.py createsuperuser

3. URLs principales:
   - Admin: http://localhost:8000/admin/
   - Register: POST http://localhost:8000/api/auth/register/
   - OAuth2 Token (password grant): POST http://localhost:8000/api/auth/token/
     - Usa `Content-Type: application/x-www-form-urlencoded`
     - Parametros: `grant_type=password`, `client_id=escoligest-angular`, `username`, `password`, `scope=read write`
     - Para refrescar, vuelve a llamar al mismo endpoint con `grant_type=refresh_token`
   - Password reset request: POST http://localhost:8000/api/auth/password-reset/request/
   - Password reset confirm: POST http://localhost:8000/api/auth/password-reset/confirm/
   - Appointments: http://localhost:8000/api/appointments/

## Enviar correos reales con SMTP personal (Gmail/Outlook)

1. Activa la verificación en dos pasos de tu cuenta y genera una *contraseña de aplicación* (Gmail: `Security > App passwords`, Outlook: `Security > Advanced security options > App passwords`).
2. Copia `.env.example` a `.env` y completa los datos de tu buzón:
   ```bash
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com          # o smtp.office365.com para Outlook/Hotmail
   EMAIL_PORT=587
   EMAIL_HOST_USER=tu_correo@gmail.com
   EMAIL_HOST_PASSWORD=<CONTRASENA_DE_APLICACION>
   EMAIL_USE_TLS=True
   EMAIL_USE_SSL=False
   DEFAULT_FROM_EMAIL=soporte@escoligest.local
   ```
3. Levanta los servicios con `docker compose up --build`. El contenedor `backend` leerá automáticamente las variables y enviará los correos de recuperación gratis a través de tu cuenta personal (respetando los límites diarios del proveedor).
4. Ejecuta el flujo “¿Olvidaste tu contraseña?” desde el frontend para validar que llega el correo con el enlace.

## Enviar correos reales con SendGrid

1. Crea una API Key en [SendGrid](https://app.sendgrid.com/settings/api_keys) con permisos “Full Access”.
2. Configura tu `.env` con los valores de SendGrid:
   ```bash
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.sendgrid.net
   EMAIL_PORT=587
   EMAIL_HOST_USER=apikey          # literal; SendGrid usa "apikey" como usuario
   EMAIL_HOST_PASSWORD=<TU_API_KEY_DE_SENDGRID>
   EMAIL_USE_TLS=True
   EMAIL_USE_SSL=False
   DEFAULT_FROM_EMAIL=soporte@escoligest.local
   ```
3. Levanta el stack o reinicia el contenedor backend para aplicar los cambios.
4. Usa el flujo de “Recuperar contraseña”; los correos saldrán vía SendGrid.

> Si necesitas un entorno de pruebas sin enviar correos reales, deja `EMAIL_BACKEND` con el valor por defecto (`django.core.mail.backends.console.EmailBackend`). De esa forma los mensajes solo se imprimen en la consola del backend.

## Recordatorios dentro de la aplicación

- Cada paciente ve una campana en el encabezado de su panel. Allí se listan todas las actividades pendientes que comienzan en los próximos 10 minutos; ese tiempo es fijo para todo el sistema.
- El backend expone automáticamente esas actividades y el frontend las consulta cada minuto, así que no necesitas programar comandos ni cron jobs adicionales.
- Los correos electrónicos solo se usan para la recuperación de contraseñas; los recordatorios regulares viven completamente dentro de la app.
