from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg

from api.database import init_pool, close_pool
from api.exceptions import postgres_exception_handler
from api.routers import salud, vinos, clientes, comprobantes, salas, transferencias, ingresos


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio: inicializar pool de conexiones
    init_pool()
    yield
    # Fin: cerrar conexiones limpiamente
    close_pool()


app = FastAPI(
    title="Bodegas del Atuel — API REST",
    description=(
        "API REST oficial para la gestión de bodegas, catálogo de vinos, clientes, "
        "comprobantes de venta transaccionales, transferencias e ingresos de Bodegas del Atuel. "
        "Diseñada para el TPI de Bases de Datos (UTN FRSR 2026)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS para permitir conexión desde el frontend (Etapa 7)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manejador global de excepciones PostgreSQL
app.add_exception_handler(psycopg.Error, postgres_exception_handler)

# Inclusión de routers
app.include_router(salud.router)
app.include_router(vinos.router)
app.include_router(clientes.router)
app.include_router(comprobantes.router)
app.include_router(salas.router)
app.include_router(transferencias.router)
app.include_router(ingresos.router)


@app.get("/", include_in_schema=False)
def root():
    return {
        "sistema": "Bodegas del Atuel - API REST",
        "version": "1.0.0",
        "documentacion": "/docs",
        "salud": "/salud",
    }
