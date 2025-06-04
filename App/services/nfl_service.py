import httpx
from fastapi import HTTPException
from App.core.config import settings

class NFLService:
    def __init__(self):
        self.base_url = settings.BASE_URL
        self.api_key = settings.API_KEY
        
    async def get_data(self, endpoint: str, params: dict = None):
        """
        Generic method to fetch data from the Fantasy Nerds NFL API
        
        Args:
            endpoint (str): The API endpoint to call
            params (dict, optional): Additional query parameters
            
        Returns:
            dict: The JSON response from the API
        """
        # Make sure endpoint doesn't start with a slash
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
            
        # Build the full URL with API key
        url = f"{self.base_url}/{endpoint}"
        
        # Prepare query parameters with the API key
        query_params = {"apikey": self.api_key}
        if params:
            query_params.update(params)
            
        # Debug log
        print(f"Calling Fantasy Nerds API: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=query_params)
                response.raise_for_status()  # Raise an exception for HTTP errors
                return response.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=408, detail=f"Request to {url} timed out")
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 401:
                detail = "API key invalid or expired"
            elif status_code == 403:
                detail = "Access forbidden. Check API subscription"
            elif status_code == 404:
                detail = f"Resource not found: {endpoint}"
            elif status_code == 429:
                detail = "Rate limit exceeded"
            else:
                detail = f"HTTP error {status_code}: {str(e)}"
            raise HTTPException(status_code=status_code, detail=detail)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
            
    async def get_teams(self):
        """
        Get a list of NFL teams and their team codes
        
        Returns:
            dict: NFL teams data
        """
        return await self.get_data("teams")
    
    async def get_schedule(self):
        """
        Retrieve the current regular season schedule
        
        Returns:
            dict: Schedule data
        """
        return await self.get_data("schedule")
    
    async def get_standings(self):
        """
        Retrieve the current regular-season standings for all NFL teams including their rankings
        within their division and conference
        
        Returns:
            dict: Season standings data
        """
        return await self.get_data("standings")

    async def get_weekly_injuries(self, season=None, week=None):
        """
        Retrieve injury reports for all NFL teams during the regular season
        
        Args:
            season (int, optional): NFL season year (e.g., 2024)
            week (int, optional): NFL week number (1-18)
        
        Returns:
            dict: Injury data
        """
        # Build query parameters based on input
        params = {}
        if season is not None:
            params["season"] = season
        if week is not None:
            params["week"] = week
            
        return await self.get_data("injuries", params)

    async def get_draft_rankings(self, format: str = "std"):
        """
        Retrieve draft rankings and injury risk for the current season
        
        Args:
            format (str): The scoring format (std, ppr, half, superflex)
            
        Returns:
            dict: Draft rankings data
        """
        params = {"format": format} if format != "std" else {}
        return await self.get_data("draft-rankings", params)

    async def get_player_tiers(self, format: str = "std"):
        """
        Retrieve player tiers for value-based drafting
        
        Args:
            format (str): The scoring format (std, ppr)
            
        Returns:
            dict: Player tiers data
        """
        params = {"format": format} if format != "std" else {}
        return await self.get_data("tiers", params)
    
    async def get_auction_values(self, teams: int = 12, budget: int = 200, format: str = "std"):
        """
        Retrieve fantasy football auction values
        
        Args:
            teams (int): Number of teams in the league (8, 10, 12, 14, 16)
            budget (int): League budget (default: 200)
            format (str): Scoring format (std, ppr)
            
        Returns:
            dict: Auction values data
        """
        params = {}
        if teams != 12:
            params["teams"] = teams
        if budget != 200:
            params["budget"] = budget
        if format != "std":
            params["format"] = format
        return await self.get_data("auction", params)
    
    async def get_adp(self, teams: int = 12, format: str = "std"):
        """
        Retrieve average draft position data
        
        Args:
            teams (int): Number of teams in the league (8, 10, 12, 14, 16)
            format (str): Scoring format (std, ppr, half, superflex)
            
        Returns:
            dict: ADP data
        """
        params = {}
        if teams != 12:
            params["teams"] = teams
        if format != "std":
            params["format"] = format
        return await self.get_data("adp", params)
    
    async def get_best_ball_rankings(self):
        """
        Retrieve Best Ball rankings for the upcoming NFL season
        
        Returns:
            dict: Best Ball rankings data
        """
        return await self.get_data("bestball")
    
    async def get_bye_weeks(self):
        """
        Retrieve bye weeks for the current season
        
        Returns:
            dict: Bye weeks data
        """
        return await self.get_data("byes")
    
    async def get_dfs(self, slate_id: str):
        """
        Get the salaries, Fantasy Nerds projected points, and Bang for Your Buck scores 
        for FanDuel, DraftKings, and Yahoo for the current week
        
        Args:
            slate_id (str): The slateId from the DFS Slates endpoint
            
        Returns:
            dict: DFS data for the specified slate
        """
        params = {"slateId": slate_id}
        return await self.get_data("dfs", params)
    
    async def get_dfs_slates(self):
        """
        Get a listing of the current slates for upcoming DFS Classic contests
        
        Returns:
            dict: DFS slates data
        """
        return await self.get_data("dfs-slates")
    
    async def get_defensive_rankings(self):
        """
        Retrieve defensive rankings for all NFL teams
        
        Returns:
            dict: Defensive rankings data
        """
        return await self.get_data("defense-rankings")
    
    async def get_depth_charts(self):
        """
        Retrieve current depth charts for all NFL teams
        
        Returns:
            dict: Depth charts data
        """
        return await self.get_data("depth")
        
    async def get_weekly_projections(self):
        """
        Retrieve weekly projections for Weeks 1-18
        
        Returns:
            dict: Weekly projections data
        """
        return await self.get_data("weekly-projections")
        
    async def get_weekly_rankings(self, format: str = "std"):
        """
        Retrieve current weekly rankings including projected points
        
        Args:
            format (str): Scoring format (std, ppr, half)
            
        Returns:
            dict: Weekly rankings data
        """
        params = {"format": format} if format != "std" else {}
        return await self.get_data("weekly-rankings", params)
    
    async def get_dynasty_rankings(self):
        """
        Retrieve consensus dynasty rankings
        
        Returns:
            dict: Dynasty rankings data
        """
        return await self.get_data("dynasty")
    
    async def get_nfl_news(self):
        """
        Retrieve current player and team news with fantasy analysis
        
        Returns:
            list: NFL news articles
        """
        return await self.get_data("news")
    
    async def get_idp_draft(self):
        """
        Retrieve IDP (Individual Defensive Players) rankings for the upcoming NFL season
        
        Returns:
            dict: IDP draft rankings data
        """
        return await self.get_data("idp-draft")
    
    async def get_idp_weekly(self):
        """
        Retrieve weekly projections for IDP players
        
        Returns:
            dict: IDP weekly projections data
        """
        return await self.get_data("idp-weekly")
    
    async def get_nfl_picks(self):
        """
        Get the current week's NFL game picks for each game broken down by expert
        
        Returns:
            dict: NFL picks data
        """
        return await self.get_data("nfl-picks")
    
    async def get_fantasy_leaders(self, format: str = "std", position: str = "ALL", week: int = 0):
        """
        Retrieve weekly and season leaders by total fantasy points
        
        Args:
            format (str): Scoring format (std, ppr, half)
            position (str): Position filter (ALL, QB, RB, WR, TE, FLEX, K, IDP)
            week (int): Week number (0 for entire season, 1-18 for specific week)
            
        Returns:
            dict: Fantasy leaders data
        """
        params = {}
        if format != "std":
            params["format"] = format
        if position != "ALL":
            params["position"] = position
        if week != 0:
            params["week"] = week
        return await self.get_data("leaders", params)

    async def get_players(self, include_inactive: bool = False):
        """
        Retrieve a list of current NFL players
        
        Args:
            include_inactive (bool): Whether to include inactive players
            
        Returns:
            dict: NFL players data
        """
        params = {}
        if include_inactive:
            params["include_inactive"] = 1
        return await self.get_data("players", params)
    
    async def get_player_adds_drops(self):
        """
        Retrieve the players most added and dropped over the previous 48 hours
        
        Returns:
            dict: Player adds and drops data
        """
        return await self.get_data("add-drops")
    
    async def get_playoff_projections(self, week: int):
        """
        Retrieve statistical projections for the NFL playoffs
        
        Args:
            week (int): Playoff week (1=Wild Card, 2=Divisional, 3=Conference Championships, 4=Super Bowl)
            
        Returns:
            dict: Playoff projections data
        """
        params = {"week": week}
        return await self.get_data("playoffs", params)
    
    async def get_weather_forecasts(self):
        """
        Retrieve the weather forecasts for all NFL teams
        
        Returns:
            dict: Weather forecasts data
        """
        return await self.get_data("weather")
    
    async def get_draft_projections(self):
        """
        Retrieve draft projections for the upcoming season
        
        Returns:
            dict: Draft projections data
        """
        return await self.get_data("draft-projections")
    
    async def get_rest_of_season_projections(self):
        """
        Retrieve rest of season (ROS) projections for all skill and IDP players
        
        Returns:
            dict: ROS projections data
        """
        return await self.get_data("ros")

nfl_service = NFLService()
