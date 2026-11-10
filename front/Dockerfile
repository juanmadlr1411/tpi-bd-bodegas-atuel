# ==========================================
# STAGE 1: Build (Compilación del Frontend)
# ==========================================
# Usamos Node 22 en su versión ligera (alpine)
FROM node:22-alpine AS build

WORKDIR /app

# Copiamos los archivos de configuración de dependencias
COPY package*.json ./

# Instalamos las dependencias de Node
RUN npm install

# Copiamos todo el código fuente del frontend
COPY . .

# Compilamos la aplicación (esto generará la carpeta /app/dist)
RUN npm run build

# ==========================================
# STAGE 2: Production (Servidor Nginx Ligero)
# ==========================================
# Usamos Nginx en versión alpine para servir los archivos estáticos
FROM nginx:alpine

# Copiamos SOLO los archivos compilados del Stage 1 a la carpeta pública de Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Exponemos el puerto 80 del contenedor (donde escucha Nginx)
EXPOSE 80