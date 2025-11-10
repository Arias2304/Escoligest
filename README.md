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

## Enviar correos reales con SendGrid

1. Crea una API Key en [SendGrid](https://app.sendgrid.com/settings/api_keys) con permisos “Full Access”.
2. Copia el archivo `.env.example` (o crea uno nuevo en la raíz del repo) y define:
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
3. Exporta esas variables en tu shell (si corres `manage.py` directo) o simplemente ejecuta `docker compose up --build`, porque `docker-compose.yml` ya reenvía dichas variables al contenedor `backend`.
4. Usa el flujo de “Recuperar contraseña” desde el frontend; los correos saldrán usando la API Key configurada.

> Si necesitas un entorno de pruebas sin enviar correos reales, deja `EMAIL_BACKEND` con el valor por defecto (`django.core.mail.backends.console.EmailBackend`). De esa forma los mensajes solo se imprimen en la consola del backend.
