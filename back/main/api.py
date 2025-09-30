# back/main/api.py
import asyncio
import traceback
import uuid
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from typing_extensions import TypedDict, Any
import sys
sys.path.append('/app')

import threading

from main import analysis_worker
from actions.llm_checks import check_pitch_dimensions_with_llm, DimensionInfo
from supabase_client import supabase

app = FastAPI()


#  --- Configuration CORS ---
origins = [
    "http://localhost:3000",
    "https://nextraction.io",# Autoriser le frontend Next.js (port par défaut)
    # Ajoutez d'autres origines si nécessaire (ex: URL de déploiement)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Les origines autorisées
    allow_credentials=True,    # Autoriser les cookies si besoin
    allow_methods=["*"],       # Autoriser toutes les méthodes (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],       # Autoriser tous les en-têtes
)
# --- Fin Configuration CORS ---
# --- State Management (In-memory) ---
# !!! Warning: This is simple in-memory storage. For production, consider Redis or a database.
# It will be lost if the server restarts. Not suitable for concurrent runs without modification
# if worker script writes to shared files like 'personas.json' without task_id scoping.
tasks: Dict[str, Dict[str, Any]] = {}

# --- Define a type for the detailed persona info (optional but good practice) ---
class PersonaCardDetails(TypedDict):
    name: str
    education: str
    hobbies: str
    job: str
    salary_range: str
    why_important: str
    needs: str
    relationship_channels: str
    # Add other fields if included in create_personas.py

class DetailedPersonaInfo(TypedDict):
    name: str
    prompt: str
    card_details: PersonaCardDetails

# --- Pydantic Models ---

class StartAnalysisRequest(BaseModel):
    user_id: str
    name: str
    industry: str
    product_description: str
    stage: str = "Idea" or "Prototype" or "MVP"

class StartAnalysisResponse(BaseModel):
    task_id: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    # Add other relevant fields you might want to expose in a status check
    error: Optional[str] = None
    final_analysis_ready: bool = False
    personas_ready: bool = False

class FinalAnalysisResponse(BaseModel):
    task_id: str
    final_analysis: str # Assuming it's a string (Markdown)

class SelectPersonaRequest(BaseModel):
    choice: int # Expecting 1, 2, 3, or 4

class SelectPersonaResponse(BaseModel):
    message: str
    selected_persona_name: str

class CheckDescriptionRequest(BaseModel):
    description: str
    # Send the dimensions from the frontend so backend knows what to check
    dimensions: List[DimensionInfo]

class CheckDescriptionResponse(BaseModel):
    coverage: Dict[str, bool] # Maps dimension_id to boolean status

class ProjectListItem(BaseModel):
    task_id: str
    product_description: str
    status: str
    creation_timestamp: str
    last_updated_timestamp: str

class ProjectListResponse(BaseModel):
    projects: List[ProjectListItem]

class ProjectDetailResponse(BaseModel):
    task_id: str
    product_description: str
    status: str
    creation_timestamp: str
    last_updated_timestamp: str
    task_dir: str
    error_message: Optional[str] = None
    final_analysis_ready: bool = False
    personas_ready: bool = False
    # Optionally include analysis/persona data if requested/ready
    final_analysis: Optional[str] = None
    persona_details: Optional[List[DetailedPersonaInfo]] = None
    selected_persona_info: Optional[Dict[str, Any]] = None # Store {choice: X, name: Y}
    chat_history: Optional[List[Dict[str, Any]]] = None

# --- API Endpoints ---


## works don't touch
@app.post("/check_description_completeness", response_model=CheckDescriptionResponse)
async def check_description_completeness(request: CheckDescriptionRequest):
    """
    Analyzes a project description against key dimensions using an LLM.
    """
    if not request.description or not request.dimensions:
        raise HTTPException(status_code=400, detail="Description and dimensions are required.")

    try:
        # Run the LLM check (this is synchronous for now, consider background task if slow)
        # Note: Ensure the function is accessible here (imported or defined above)
        coverage_results = check_pitch_dimensions_with_llm(
            user_description=request.description,
            dimensions=request.dimensions
        )
        return CheckDescriptionResponse(coverage=coverage_results)
    except Exception as e:
        # Log the exception details on the server
        print(f"ERROR during description check: {e}\n{traceback.format_exc()}") # Or use proper logging
        raise HTTPException(status_code=500, detail=f"Failed to analyze description: {e}")

## added project_id, still need to see if it works once connected to frontend
## we still need to modify this endpoint to handle project_id correctly and save to DB instead of just returning task_id
@app.post("/start_analysis")
async def start_analysis(request: StartAnalysisRequest, background_tasks: BackgroundTasks):
    """Starts the analysis job in the background."""
    task_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    try:
        # Save initial project to Supabase
        supabase.table("projects").insert({
            "id": project_id,
            "stage": request.stage,
            "user_id": request.user_id,
            "name": request.name,
            "industry": request.industry,
            "description": request.product_description,
            "status": "pending"
        }).execute()
    except Exception as e:
        print(f"CRITICAL: Failed to insert into Supabase: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project.")

    # Start analysis in a separate thread (for Cloud Run)
    thread = threading.Thread(
        target=run_analysis_wrapper,
        args=(request.product_description, request.name, task_id, project_id)
    )
    thread.daemon = True
    thread.start()

    return StartAnalysisResponse(task_id=task_id)

def run_analysis_wrapper(product_description, name, task_id, project_id):
    """Wrapper to run analysis in a thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def update_status_callback(task_id, status=None, data_key=None, data_value=None):
        """Callback to update task status - simplified for current implementation."""
        print(f"[STATUS UPDATE] Task {task_id}: {status}")
        # Could be extended to update in-memory task store or database if needed

    def log_callback(task_id, message):
        """Callback to log messages."""
        print(f"[LOG] Task {task_id}: {message}")

    try:
        analysis_worker.run_analysis_job(
            product_description=product_description,
            task_id=task_id,
            project_id=project_id,
            name=name,
            update_status_callback=update_status_callback,
            log_callback=log_callback,
            loop=loop
        )
    except Exception as e:
        print(f"Analysis failed for task {task_id}: {e}")
        # Update Supabase with error status
        try:
            supabase.table("projects").update({
                "status": "failed",
                "error": str(e)
            }).eq("id", project_id).execute()
        except:
            pass

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy"}
