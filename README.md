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
   - Token: POST http://localhost:8000/api/auth/token/
   - Appointments: http://localhost:8000/api/appointments/
