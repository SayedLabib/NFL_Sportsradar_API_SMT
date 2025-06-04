# Migration to Fantasy Nerds API

This document summarizes the changes made to migrate the codebase from SportsRadar API to Fantasy Nerds API.

## Key Changes

1. **API Configuration**
   - Updated `config.py` to use Fantasy Nerds base URL: https://api.fantasynerds.com/v1/nfl
   - Set default API key to "ABWTFKDMZU3G6SDPGMMY"
   - Updated application description and version

2. **API Service Layer**
   - Modified `nfl_service.py` to adapt to Fantasy Nerds API structure
   - Updated all endpoint methods to match Fantasy Nerds format
   - Added support for query parameters in API requests
   - Added new Fantasy Nerds-specific API endpoints:
     - Draft Rankings and Projections
     - Player Tiers
     - Auction Values
     - ADP (Average Draft Position)
     - Best Ball Rankings
     - Dynasty Rankings
     - Defensive Rankings
     - Weekly Projections and Rankings
     - Player News and Injury Reports
     - Fantasy Leaders
     - Player Adds/Drops
     - Weather Forecasts
     - Rest-of-Season Projections

3. **API Client Layer**
   - Updated `api_client.py` to handle the new endpoint structure
   - Added support for parameters in client requests
   - Added new Fantasy Nerds API client methods matching the service layer
   - Removed endpoints not supported by Fantasy Nerds API
     - Team profile endpoints
     - Player profile endpoints
     - Game boxscore endpoints

4. **API Routes**
   - Updated API routes in `api_routes.py` to match Fantasy Nerds API exactly
   - Removed year/season/week parameters where not needed
   - Fixed endpoint path inconsistencies (depth-charts → depth, dynasty-rankings → dynasty)
   - Added new routes for fantasy-specific endpoints

5. **Query Service**
   - Enhanced `Nfl_query_service.py` to leverage Fantasy Nerds data
   - Updated query classification to recognize fantasy-specific queries
   - Expanded data sources for more comprehensive responses

6. **Documentation**
   - Updated README.md with Fantasy Nerds API details
   - Added .env.sample file for configuration guidance
   - Updated test_api.py to demonstrate Fantasy Nerds endpoints

## Testing

1. Run the test script to verify API connectivity:
```
python test_api.py
```

2. Start the API server:
```
uvicorn main:app --reload
```

3. Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Removed Endpoints

The following endpoints were removed as they're not directly available in Fantasy Nerds API:
- `/nfl/teams/{team_id}` - Team profile endpoint
- `/nfl/players/{player_id}` - Player profile endpoint
- `/nfl/games/{game_id}/boxscore` - Game boxscore endpoint

## Path Changes

The following endpoint paths were updated to match Fantasy Nerds API exactly:
- `/nfl/depth-charts` → `/nfl/depth`
- `/nfl/dynasty-rankings` → `/nfl/dynasty`

## Added Endpoints

The following new endpoints were added:
- `/nfl/players` - Get all NFL players list
- `/nfl/add-drops` - Get player adds/drops
- `/nfl/weather` - Get weather forecasts
- `/nfl/draft-projections` - Get draft projections
- `/nfl/ros` - Get rest-of-season projections

## Notes

- Fantasy Nerds API structure differs from SportsRadar in several ways:
  - Different endpoint naming and paths
  - Different parameter requirements
  - Different response structure
- The natural language query service has been enhanced to leverage all new fantasy data
- The API is now more focused on fantasy football analytics rather than general NFL data
