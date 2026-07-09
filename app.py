import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# Ensure current directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from matching_engine import B2BMatchingEngine

app = FastAPI(title="B2B Matching Engine API", description="API for matching buyers with B2B suppliers")

# Path to the data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "Business_dataset.csv")

# Initialize matching engine
engine = B2BMatchingEngine(csv_path=CSV_PATH)
try:
    engine.load_data()
    # Build index asynchronously or synchronously on startup
    # Since example_data.csv is tiny (4 rows), building index is instantaneous.
    # For large datasets (80k rows), this would be pre-built and loaded, but this works perfectly for prototype validation.
    engine.build_index()
except Exception as e:
    print(f"Error initializing B2B Matching Engine: {e}")

class MatchRequest(BaseModel):
    query: str = Field(..., description="The buyer intent request (e.g. from Facebook post)")
    w_semantic: float = Field(0.5, description="Weight of semantic SBERT score")
    w_lexical: float = Field(0.3, description="Weight of lexical keyword match score")
    w_location: float = Field(0.2, description="Weight of geographical proximity score")
    min_score: float = Field(0.3, description="Threshold minimum combined score")

class MatchResponseItem(BaseModel):
    company: Dict[str, Any]
    score_breakdown: Dict[str, float]
    total_score: float

@app.get("/api/companies", response_model=List[Dict[str, Any]])
def get_companies():
    """Lists all loaded companies in the database (for spot checks)."""
    return engine.companies

@app.post("/api/match", response_model=List[MatchResponseItem])
def match_buyer_needs(request: MatchRequest):
    """Matches a buyer request query against the company database using adjustable weights."""
    try:
        results = engine.match(
            query=request.query,
            w_semantic=request.w_semantic,
            w_lexical=request.w_lexical,
            w_location=request.w_location,
            min_score=request.min_score
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serves the main tuning dashboard UI."""
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Dashboard UI template index.html not found.")
        
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True, ws="none")
