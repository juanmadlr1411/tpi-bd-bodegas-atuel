# Usamos la imagen oficial de Python 3.12 en su versión ligera
FROM python:3.12-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos el archivo de requerimientos desde la raíz
COPY requirements.txt .

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código de la carpeta api al contenedor
COPY api/ ./api/

# Exponemos el puerto que usa FastAPI
EXPOSE 8000

# Comando por defecto para arrancar la aplicación
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]