from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .api.chat import router as chat_router
from .api.ingest import router as ingest_router
from .api.company_search import router as company_search_router
from .api.sec_documents import router as sec_documents_router
from .api.admin import router as admin_router
from .core.globals import initialize_kernel, set_agent_registry

try:
    from .agents.registry import AgentRegistry
except ImportError:
    AgentRegistry = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    kernel = initialize_kernel()
    if AgentRegistry:
        try:
            config_path = "app/agents/agent_configs.yaml"
            agent_registry = await AgentRegistry.create_from_yaml(kernel, config_path)
            set_agent_registry(agent_registry)
            print("SK Agent Registry initialized successfully")
        except Exception as e:
            print(f"Warning: Could not initialize SK Agent Registry: {e}")
    
    yield

app = FastAPI(title="Adaptive RAG Workbench", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
app.include_router(company_search_router, prefix="/api/companies")
app.include_router(sec_documents_router)
app.include_router(admin_router, prefix="/api")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Adaptive RAG Workbench API", "version": "1.0.0"}
