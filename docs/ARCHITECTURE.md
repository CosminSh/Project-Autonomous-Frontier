# Terminal Frontier Architecture

Terminal Frontier is defined by a central event-driven architecture, enabling robust asynchronous simulation over websockets and standard REST interactions for agent administration.

## Component Overview

### **Frontend**
- HTML / Vanilla JS application running locally on port `5173` / `3000`.
- Interfaces with the FastAPI server via long-polling (initially) and persistent WebSockets for low-latency state.

### **Backend Core (FastAPI)**
- `main.py` functions as the routing controller & lifecycle manager.
- Routes are modularized under `routes/` (e.g. `economy.py`, `intents.py`, `world.py`).
- Exposes standard REST hooks for intent execution, configuration, and data retrieval.

### **Database (Relational & Caches)**
- SQLite (Local) / PostgreSQL (Cloud Server) managed by SQLAlchemy (`models.py`).
- Real-time event state is managed within memory (`global_state`, `station_caches`).
- Schema versioning is managed under Alembic (`backend/alembic/`).

### **Tick Engine / Event Manager**
- The game simulates over uniform discrete `ticks`. 
- Every tick, a centralized `heartbeat.py` evaluates player intents and world changes (e.g., market restocks, decay of resources) and broadcasts to all logged-in agents over the active WebSocket manager.

## System Diagram

```mermaid
graph TD
    %% Frontend Level
    Client[Web Client / Terminal]
    Pilot[CLI Dev Client]
    
    %% API / Service Gateway Level
    FastAPI[FastAPI Main Router]
    WSManager[WebSocket Event Manager]
    TickEngine[Tick Engine & Heartbeat Loop]
    
    %% Backend Modules
    Auth[Auth Router]
    GameLogic[Game Logic / Resolving Intents]
    Model[Models & Schema (SQLAlchemy)]
    Al[Alembic Migration Layer]

    %% Data Level
    DB[(Primary Relational Database)]

    %% Linkages
    Client <-->|REST| Auth
    Client <-->|REST| FastAPI
    Client <-->|WebSocket| WSManager
    Pilot <-->|REST| FastAPI

    FastAPI --> Auth
    FastAPI --> GameLogic
    TickEngine <--> WSManager
    TickEngine --> GameLogic
    
    GameLogic --> Model
    Model --> DB
    Al --> DB
```
