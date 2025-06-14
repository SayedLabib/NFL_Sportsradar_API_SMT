# filepath: d:\My works(Fuad)\NFL_Allsports_API\App\services\LLm_service.py
import os
import json
import httpx
import hashlib
import time
from typing import Dict, List, Any, Union
from App.core.config import settings

llm_cache = {}
LLM_CACHE_TTL = 60 * 10  # 10 minutes

class LLMService:
    def __init__(self):
        self.api_key = settings.GPT_API_KEY  # Using GPT API key from .env file
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4.1-2025-04-14"

    async def generate_response(self, query: str, context_data: Dict[str, Any] = None) -> str:
        """
        Generate a response using OpenAI's GPT model based on the user query and NFL data context
        
        Args:
            query (str): The user's query about NFL data
            context_data (dict): NFL data to provide as context to the LLM
            
        Returns:
            str: The LLM's response
        """
        # Create a cache key based on query and context
        cache_key = hashlib.sha256((query + str(context_data)).encode()).hexdigest()
        now = time.time()
        # Check cache
        if cache_key in llm_cache:
            cached_time, cached_response = llm_cache[cache_key]
            if now - cached_time < LLM_CACHE_TTL:
                return cached_response

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Extract information about which endpoints were used
        endpoints_used = []
        if context_data:
            for key in context_data:
                if key not in ["query_type", "metadata", "original_query"]:
                    # Convert the key to an endpoint name format
                    endpoint_name = key.replace("_", "-") if key != "league" else "teams"
                    endpoints_used.append(endpoint_name)
        
        # Create a string list of endpoints for the context
        endpoints_str = ", ".join([f'"/nfl/{endpoint}"' for endpoint in endpoints_used])
          # Preparing the system messages for reply
        system_message = (
            "You are an NFL analytics expert providing insights primarily based on the official Fantasy Nerds NFL data provided to you. "
            "PRIMARY STRATEGY: First prioritize analyzing Fantasy Nerds API data and extracting all relevant insights. If the requested information "
            "is not available in the Fantasy Nerds data, transition to using your own NFL knowledge base to provide valuable analysis. "
            "NEVER respond with 'I don't have enough information' or 'I can't answer that.' Instead, provide the best possible answer using available data or your knowledge.\n\n"
            "Response strategy:\n"
            "1. FIRST PRIORITY: Use the Fantasy Nerds data when available - cite specific statistics, rankings, and metrics from this data\n"
            "2. SECOND PRIORITY: When Fantasy Nerds data is limited or doesn't contain information requested:\n"
            "   a. Clearly state: 'The specific data requested isn't available in the Fantasy Nerds data. However, I can provide analysis based on general NFL knowledge.'\n"
            "   b. Provide comprehensive reasoning and knowledge about the topic to give the user helpful information\n"
            "   c. Draw on historical NFL trends, player performance patterns, and strategic football concepts\n"
            "   d. Make it clear which parts of your answer are from Fantasy Nerds data vs. general knowledge\n"
            "3. Identify trends and insights that are directly observable in the data\n"
            "4. Make logical inferences that are clearly supported by the available data\n"
            "5. For player-specific queries, if the player isn't found in Fantasy Nerds data:\n"
            "   a. State: 'This player doesn't appear in the current Fantasy Nerds data. Here's what I know about them:'\n"
            "   b. Provide detailed player analysis including position, team, playing style, recent performance, and fantasy relevance\n"
            "6. For fantasy advice queries, prioritize Fantasy Nerds data but supplement with detailed strategy knowledge when helpful\n"
            "7. Include a line at the end that says: 'Primary data sourced from Fantasy Nerds API: ' followed by a list of "
            f"the specific endpoints that were used: {endpoints_str}\n"
            "Remember to always be transparent about the source of your information (Fantasy Nerds API vs general knowledge)."
        )
        
        messages = [{"role": "system", "content": system_message}]
        
        # Process context data if available - with size limitation
        if context_data:
            # Summarize the data to avoid 413 errors
            summarized_data = self._summarize_context_data(context_data)
              # Add instructions on how to use the data
            data_instructions = (
                "The following NFL data from Fantasy Nerds API should be your PRIMARY source for answering the user's query. "
                "ANALYSIS APPROACH:\n"
                "1. FIRST: Thoroughly analyze this Fantasy Nerds data and extract all relevant information to answer the query.\n"
                "2. WHEN DATA IS AVAILABLE: Use this data as your authoritative source - be specific and precise with statistics, player names, and metrics.\n"
                "3. WHEN DATA IS INCOMPLETE: Clearly indicate what information is missing from Fantasy Nerds data, then provide your own analysis.\n"
                "4. WHEN DATA IS ABSENT: State 'This specific information isn't available in the Fantasy Nerds data' and then use your NFL knowledge base to provide a comprehensive answer.\n\n"
                "When the data contains multiple types of information (like standings, schedules, player info), "
                "integrate them for a comprehensive analysis. "
                "For any rankings or statistics, cite specific numbers and player names exactly as they appear in the data. "
                "IMPORTANT: When discussing player rankings, explicitly name the players from the data with their exact ranks, teams, and other available details. "
                "Do not use placeholders like [Player Name]. When answering questions about specific players, extract their information from the draft_rankings or weekly_rankings sections. "
                "If you can't find a specific player in the data, clearly state: 'This player doesn't appear in the current Fantasy Nerds data' and then provide general information about the player."
            )
            
            messages.append({"role": "system", "content": data_instructions})
            
            # Format and add the summarized context data
            context_str = f"{json.dumps(summarized_data, indent=2)}"            # Limit context string to avoid payload too large - increased for better VORP calculations
            if len(context_str) > 25000:  # Increased size to allow more player data for VORP calculations
                context_str = context_str[:25000] + "...[additional data truncated for size]"
                
            messages.append({"role": "system", "content": context_str})
            print(f"Context data size after summary: {len(context_str)} characters")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": messages + [{"role": "user", "content": query}],
                        "temperature": 0.7,
                        "max_tokens": 800,  # Increased for more detailed responses
                    },
                )
                response.raise_for_status()
                
                result = response.json()
                llm_response = result['choices'][0]['message']['content']
                # Store in cache
                llm_cache[cache_key] = (now, llm_response)
                return llm_response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return "Rate limit exceeded. Please try again later."
            print(f"Error generating response: {e}")
            return f"Sorry, I couldn't generate a response: {str(e)}"
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Sorry, I couldn't generate a response: {str(e)}"

    def _summarize_context_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize the context data to a reasonable size for the LLM API, 
        handling combined data from multiple endpoints        """
        # Create a container for the summarized data
        summarized = {
            "query_type": data.get("query_type", "unknown"),
            "metadata": data.get("metadata", {})
        }
        
        try:
            # Process each type of data in the combined data
            if "league" in data:
                summarized["league_structure"] = self._summarize_league_structure(data["league"])
                
            if "standings" in data:
                summarized["standings"] = self._summarize_standings_data(data["standings"])
                
            if "schedule" in data:
                summarized["schedule"] = self._summarize_schedule_data(data["schedule"])
                
            if "team_profiles" in data:
                summarized["team_profiles"] = {}
                for team_code, profile in data["team_profiles"].items():
                    summarized["team_profiles"][team_code] = self._summarize_team_profile(profile)
                    
            if "injuries" in data:
                summarized["injuries"] = self._summarize_injury_data(data["injuries"])
                
            if "team_injuries" in data:
                summarized["team_injuries"] = {}
                for team_code, injuries in data["team_injuries"].items():
                    summarized["team_injuries"][team_code] = self._summarize_team_injuries(injuries)
                    
            if "relevant_games" in data:
                summarized["relevant_games"] = self._summarize_games(data["relevant_games"])
                
            if "team_games" in data:
                summarized["team_games"] = {}
                for team_code, games in data["team_games"].items():
                    summarized["team_games"][team_code] = self._summarize_games(games)
                    
            if "boxscore" in data:
                summarized["boxscore"] = self._summarize_boxscore(data["boxscore"])
                  # Handle draft rankings data
            if "draft_rankings" in data:
                summarized["draft_rankings"] = self._summarize_fantasy_rankings(data["draft_rankings"])
                  
            # Handle weekly rankings data  
            if "weekly_rankings" in data:
                summarized["weekly_rankings"] = self._summarize_fantasy_rankings(data["weekly_rankings"])
                
            # Handle ROS projections data (position-keyed structure)
            if "ros_projections" in data:
                summarized["ros_projections"] = self._summarize_ros_projections(data["ros_projections"])
                  # Handle news data
            if "news" in data:
                summarized["news"] = self._summarize_news_data(data["news"])
                
            # Handle ADP data
            if "adp" in data:
                summarized["adp"] = self._summarize_fantasy_rankings(data["adp"])
                
            # Handle player tiers data
            if "player_tiers" in data:
                summarized["player_tiers"] = self._summarize_fantasy_rankings(data["player_tiers"])
                
            # Handle auction values data
            if "auction_values" in data:
                summarized["auction_values"] = self._summarize_fantasy_rankings(data["auction_values"])
                
            # Handle best ball rankings data
            if "best_ball" in data:
                summarized["best_ball"] = self._summarize_fantasy_rankings(data["best_ball"])
                
            # Handle dynasty rankings data
            if "dynasty" in data:
                summarized["dynasty"] = self._summarize_fantasy_rankings(data["dynasty"])
                
            # Handle fantasy leaders data
            if "fantasy_leaders" in data:
                summarized["fantasy_leaders"] = self._summarize_fantasy_rankings(data["fantasy_leaders"])
                
            # Handle players data
            if "players" in data:
                summarized["players"] = self._summarize_players_data(data["players"])
                  # Handle depth charts data
            if "depth" in data:
                summarized["depth"] = self._summarize_depth_charts(data["depth"])
            elif "depth_charts" in data:
                summarized["depth"] = self._summarize_depth_charts(data["depth_charts"])
                
            # Handle weekly projections data
            if "weekly_projections" in data:
                summarized["weekly_projections"] = self._summarize_fantasy_rankings(data["weekly_projections"])
                
            # Handle defensive rankings data
            if "defense_rankings" in data:
                summarized["defense_rankings"] = self._summarize_fantasy_rankings(data["defense_rankings"])
                
            # Handle bye weeks data
            if "bye_weeks" in data:
                summarized["bye_weeks"] = self._summarize_bye_weeks(data["bye_weeks"])
                
            # Handle add/drops data
            if "add_drops" in data:
                summarized["add_drops"] = self._summarize_add_drops(data["add_drops"])
                
            # Handle weather data
            if "weather" in data:
                summarized["weather"] = self._summarize_weather_data(data["weather"])
                
            # Handle draft projections data
            if "draft_projections" in data:
                summarized["draft_projections"] = self._summarize_draft_projections(data["draft_projections"])
                
            # Handle DFS data
            if "dfs" in data:
                summarized["dfs"] = self._summarize_dfs_data(data["dfs"])
                
            # Handle DFS slates data
            if "dfs_slates" in data:
                summarized["dfs_slates"] = self._summarize_dfs_slates(data["dfs_slates"])
                
            # Handle IDP draft data
            if "idp_draft" in data:
                summarized["idp_draft"] = self._summarize_fantasy_rankings(data["idp_draft"])
                
            # Handle IDP weekly data
            if "idp_weekly" in data:
                summarized["idp_weekly"] = self._summarize_fantasy_rankings(data["idp_weekly"])
                
            # Handle NFL picks data
            if "nfl_picks" in data:
                summarized["nfl_picks"] = self._summarize_nfl_picks(data["nfl_picks"])                
            return summarized
        except Exception as e:
            print(f"Error during data summarization: {e}")
            print(f"DEBUG: Error traceback: {type(e).__name__}: {str(e)}")
            # Let's see which data key was being processed
            import traceback
            traceback.print_exc()
            return {"summary": "Data available but could not be summarized due to an error",
                    "error": str(e)}

    def _summarize_league_structure(self, league_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize league structure data"""
        if not league_data:
            return {}
        
        # Handle if league_data is a list (like teams endpoint)
        if isinstance(league_data, list):
            summary = {
                "league_name": "NFL",
                "teams_count": len(league_data),
                "teams_sample": []
            }
            
            # Take a sample of teams
            for team in league_data[:10]:  # Limit to 10 teams
                if isinstance(team, dict):
                    summary["teams_sample"].append({
                        "name": team.get("name", ""),
                        "market": team.get("market", ""),
                        "alias": team.get("alias", ""),
                        "conference": team.get("conference", ""),
                        "division": team.get("division", "")
                    })
            
            return summary
            
        # Handle if league_data is a dict (hierarchical structure)
        summary = {
            "league_name": league_data.get("name", "NFL"),
            "conferences": []
        }
        
        try:
            if "conferences" in league_data:
                for conference in league_data["conferences"]:
                    conf_summary = {
                        "name": conference.get("name", ""),
                        "alias": conference.get("alias", ""),
                        "divisions": []
                    }
                    
                    for division in conference.get("divisions", []):
                        div_summary = {
                            "name": division.get("name", ""),
                            "alias": division.get("alias", ""),
                            "teams": []
                        }
                        
                        for team in division.get("teams", []):
                            div_summary["teams"].append({
                                "name": team.get("name", ""),
                                "market": team.get("market", ""),
                                "alias": team.get("alias", "")
                            })
                        
                        conf_summary["divisions"].append(div_summary)
                    
                    summary["conferences"].append(conf_summary)
            
            return summary
        except Exception as e:
            print(f"Error summarizing league structure: {e}")
            return {"summary": "League structure data available but could not be summarized"}

    def _summarize_team_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize team profile data to essential information"""
        if not profile_data:
            return {}
            
        summary = {
            "team_info": {},
            "coaches": [],
            "key_players": []
        }
        
        try:
            # Basic team info
            summary["team_info"] = {
                "id": profile_data.get("id", ""),
                "name": profile_data.get("name", ""),
                "market": profile_data.get("market", ""),
                "alias": profile_data.get("alias", ""),
                "conference": profile_data.get("conference", ""),
                "division": profile_data.get("division", "")
            }
            
            # Coaches
            if "coaches" in profile_data:
                for coach in profile_data["coaches"][:3]:  # Limit to 3 coaches
                    summary["coaches"].append({
                        "name": coach.get("name", ""),
                        "position": coach.get("position", ""),
                        "experience": coach.get("experience", "")
                    })
            
            # Key players (limited to 10)
            if "players" in profile_data:
                for player in sorted(profile_data["players"], 
                                   key=lambda p: p.get("depth", 99))[:10]:  # Top 10 on depth chart
                    summary["key_players"].append({
                        "name": player.get("name", ""),
                        "position": player.get("position", ""),
                        "jersey_number": player.get("jersey_number", ""),
                        "depth": player.get("depth", 0)
                    })
            
            return summary
        except Exception as e:
            print(f"Error summarizing team profile: {e}")
            return {"summary": "Team profile data available but could not be summarized"}
    
    def _summarize_team_injuries(self, injuries_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize team injuries data"""
        if not injuries_data:
            return {}
            
        summary = {
            "team": injuries_data.get("name", ""),
            "alias": injuries_data.get("alias", ""),
            "injured_players": []
        }
        
        try:
            if "players" in injuries_data:
                for player in injuries_data["players"][:10]:  # Limit to 10 players
                    summary["injured_players"].append({
                        "name": player.get("name", ""),
                        "position": player.get("position", ""),
                        "status": player.get("status", ""),
                        "injury": player.get("injury", "")
                    })
            
            return summary
        except Exception as e:
            print(f"Error summarizing team injuries: {e}")
            return {"summary": "Team injuries data available but could not be summarized"}
    
    def _summarize_games(self, games_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Summarize a list of games"""
        if not games_data:
            return []
            
        games_summary = []
        
        try:
            # Take up to 10 games to show more complete schedule
            for game in games_data[:10]:
                # Handle both new and old data structures
                home_team_info = game.get("home_team", "")
                away_team_info = game.get("away_team", "")
                
                # If direct fields don't exist, try nested structure
                if not home_team_info:
                    home_team_info = game.get("home", {}).get("alias", "")
                if not away_team_info:
                    away_team_info = game.get("away", {}).get("alias", "")
                
                game_summary = {
                    "gameId": game.get("gameId", game.get("id", "")),
                    "week": game.get("week", ""),
                    "game_date": game.get("game_date", game.get("scheduled", "")),
                    "home_team": home_team_info,
                    "away_team": away_team_info,
                    "tv_station": game.get("tv_station", ""),
                    "home_score": game.get("home_score", game.get("home_points", 0)),
                    "away_score": game.get("away_score", game.get("away_points", 0)),
                    "status": game.get("status", "Scheduled")
                }
                games_summary.append(game_summary)
            
            return games_summary
        except Exception as e:
            print(f"Error summarizing games: {e}")
            return [{"summary": "Games data available but could not be summarized"}]
    
    def _summarize_standings_data(self, standings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize standings data to essential rankings information"""
        if not standings_data:
            return {}
            
        summary = {
            "season": standings_data.get("season", {}).get("year", ""),
            "conferences": []
        }
        
        try:
            if "conferences" in standings_data:
                for conference in standings_data["conferences"]:
                    conf_summary = {
                        "name": conference.get("name", ""),
                        "alias": conference.get("alias", ""),
                        "divisions": []
                    }
                    
                    for division in conference.get("divisions", []):
                        div_summary = {
                            "name": division.get("name", ""),
                            "alias": division.get("alias", ""),
                            "teams": []
                        }
                        
                        for team in division.get("teams", []):
                            div_summary["teams"].append({
                                "name": team.get("name", ""),
                                "alias": team.get("alias", ""),
                                "wins": team.get("wins", 0),
                                "losses": team.get("losses", 0),
                                "ties": team.get("ties", 0),
                                "win_pct": team.get("win_pct", 0),                                "points_for": team.get("points_for", 0),
                                "points_against": team.get("points_against", 0)
                            })
                        
                        conf_summary["divisions"].append(div_summary)
                    
                    summary["conferences"].append(conf_summary)
            
            return summary
        except Exception as e:
            print(f"Error summarizing standings: {e}")
            return {"summary": "Standings data available but could not be summarized"}

    def _summarize_schedule_data(self, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize schedule data to essential games info"""
        try:
            # Handle if the data is a list directly (some Fantasy Nerds endpoints return lists)
            if isinstance(data, list):
                summarized = {
                    "year": "current",
                    "type": "regular",
                    "games": []
                }
                # If it's a list, treat it as a list of games
                games = data[:10]  # Limit to 10 games
            else:
                # Handle dictionary format
                summarized = {
                    "year": data.get("year", ""),
                    "type": data.get("type", ""),
                    "games": []
                }
                # Take only the first 10 games to limit size
                games = data.get("games", [])[:10]
            
            for game in games:
                if isinstance(game, dict):
                    game_summary = {
                        "gameId": game.get("gameId", game.get("id", "")),
                        "season": game.get("season", ""),
                        "week": game.get("week", ""),
                        "game_date": game.get("game_date", game.get("scheduled", "")),
                        "home_team": game.get("home_team", game.get("home", {}).get("alias", "")),
                        "away_team": game.get("away_team", game.get("away", {}).get("alias", "")),
                        "home_score": game.get("home_score", game.get("home_points", None)),
                        "away_score": game.get("away_score", game.get("away_points", None)),
                        "tv_station": game.get("tv_station", ""),
                        "winner": game.get("winner", None)
                    }
                    summarized["games"].append(game_summary)
            
            return summarized
        except Exception as e:
            print(f"Error summarizing schedule data: {e}")
            return {"summary": "Schedule data available but could not be summarized"}

    def _summarize_injury_data(self, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize injury report data"""
        try:
            # Handle if the data is a list directly (some Fantasy Nerds endpoints return lists)
            if isinstance(data, list):
                summarized = {
                    "week": "current",
                    "teams_with_injuries": []
                }
                # If it's a list, treat it as a list of teams or players
                teams = data[:10]  # Limit to 10 teams
            else:
                # Handle dictionary format
                summarized = {
                    "week": data.get("week", ""),
                    "teams_with_injuries": []
                }
                teams = data.get("teams", [])[:10]  # Limit to 10 teams
            for team in teams:
                team_summary = {
                    "name": team.get("name", ""),
                    "alias": team.get("alias", ""),
                    "injuries": []
                }
                
                # Limit to 10 players per team
                players = team.get("players", [])[:10]
                for player in players:
                    player_summary = {
                        "name": player.get("name", ""),
                        "position": player.get("position", ""),
                        "status": player.get("status", ""),
                        "injury": player.get("injury", "")
                    }
                    team_summary["injuries"].append(player_summary)
                
                summarized["teams_with_injuries"].append(team_summary)
            
            return summarized
        except Exception as e:
            print(f"Error summarizing injury data: {e}")
            return {"summary": "Injury data available but could not be summarized"}

    def _summarize_boxscore(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize boxscore data"""
        summarized = {
            "id": data.get("id", ""),
            "status": data.get("status", ""),
            "scheduled": data.get("scheduled", ""),
            "home": {
                "name": data.get("home", {}).get("name", ""),
                "alias": data.get("home", {}).get("alias", ""),
                "points": data.get("home_points", 0),
                "scoring": data.get("home", {}).get("scoring", []),
                "statistics": self._extract_key_stats(data.get("home", {}).get("statistics", {}))
            },
            "away": {
                "name": data.get("away", {}).get("name", ""),
                "alias": data.get("away", {}).get("alias", ""),
                "points": data.get("away_points", 0),
                "scoring": data.get("away", {}).get("scoring", []),
                "statistics": self._extract_key_stats(data.get("away", {}).get("statistics", {}))
            }
        }
        return summarized

    def _extract_key_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key team statistics from boxscore"""
        key_stats = {}
        
        if not stats:
            return key_stats
            
        # Team totals
        if "team" in stats:
            team = stats["team"]
            key_stats["team"] = {
                "first_downs": team.get("first_downs", 0),
                "total_yards": team.get("total_yards", 0),
                "penalties": team.get("penalties", 0),
                "penalty_yards": team.get("penalty_yards", 0),
                "turnovers": team.get("turnovers", 0),
                "time_of_possession": team.get("possession_time", "")
            }
        
        # Passing stats
        if "passing" in stats:
            key_stats["passing"] = {
                "completions": stats["passing"].get("completions", 0),
                "attempts": stats["passing"].get("attempts", 0),
                "yards": stats["passing"].get("yards", 0),
                "touchdowns": stats["passing"].get("touchdowns", 0),
                "interceptions": stats["passing"].get("interceptions", 0)
            }
        
        # Rushing stats
        if "rushing" in stats:
            key_stats["rushing"] = {
                "attempts": stats["rushing"].get("attempts", 0),
                "yards": stats["rushing"].get("yards", 0),
                "touchdowns": stats["rushing"].get("touchdowns", 0)
            }
        
        # Receiving stats
        if "receiving" in stats:
            key_stats["receiving"] = {
                "receptions": stats["receiving"].get("receptions", 0),
                "yards": stats["receiving"].get("yards", 0),
                "touchdowns": stats["receiving"].get("touchdowns", 0)
            }
        
        return key_stats

    def _create_generic_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a generic summary for unrecognized data formats"""
        summary = {"data_summary": "NFL data available"}
        
        # Try to extract some useful information
        if isinstance(data, dict):
            # Extract top-level keys and some values
            keys = list(data.keys())[:10]  # First 10 keys
            summary["available_data"] = keys
            
            # If there are lists, report their sizes
            for key in keys:
                if isinstance(data[key], list):
                    summary[f"{key}_count"] = len(data[key])                    # Sample a few items if they're dictionaries
                    if data[key] and isinstance(data[key][0], dict):
                        sample_keys = list(data[key][0].keys())[:5]
                        summary[f"{key}_contains"] = sample_keys
        
        return summary

    def _summarize_fantasy_rankings(self, rankings_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Summarize fantasy rankings data (draft rankings or weekly rankings)
        Can handle both list and dictionary responses from the Fantasy Nerds API
        """
        print(f"DEBUG: _summarize_fantasy_rankings called with data type: {type(rankings_data)}")
        if isinstance(rankings_data, list) and rankings_data:
            print(f"DEBUG: First list item type: {type(rankings_data[0])}")
        elif isinstance(rankings_data, dict):
            print(f"DEBUG: Dict keys: {list(rankings_data.keys())}")
            
        if not rankings_data:
            return {"summary": "No rankings data available"}
            
        try:
            # Handle if the response is a list of players
            if isinstance(rankings_data, list):
                print(f"DEBUG: Handling list format with {len(rankings_data)} items")                # Take more players to enable VORP calculations (need ~25 for QB position analysis)
                top_players = rankings_data[:25]
                summarized = []
                
                for player in top_players:
                    # Ensure player is a dictionary before trying to access its attributes
                    if not isinstance(player, dict):
                        print(f"DEBUG: Skipping non-dict player data: {type(player)} - {str(player)[:100]}")
                        continue
                        
                    player_summary = {
                        "id": player.get("player_id", ""),
                        "name": player.get("display_name", player.get("name", "")),
                        "team": player.get("team", ""),
                        "position": player.get("position", ""),
                        "rank": player.get("rank", player.get("position_rank", 0)),
                        "bye_week": player.get("bye_week", "")
                    }
                      # Include projected points if available (common in weekly rankings)
                    if "standard_points" in player:
                        player_summary["projected_points"] = {
                            "standard": player.get("standard_points", 0),
                            "ppr": player.get("ppr_points", 0),
                            "half_ppr": player.get("half_ppr_points", 0)
                        }
                    
                    # Include projected points if available (critical for VORP calculations)
                    if "proj_pts" in player:
                        player_summary["projected_points"] = player.get("proj_pts", 0)
                    
                    # Include ADP data if available (common in draft rankings)
                    if "adp" in player:
                        player_summary["adp"] = player.get("adp", 0)
                    
                    # Include injury risk if available
                    if "injury_risk" in player:
                        player_summary["injury_risk"] = player.get("injury_risk", "")
                        
                    summarized.append(player_summary)
                
                return summarized
                
            # Handle if the response is a dictionary with positions as keys
            elif isinstance(rankings_data, dict):
                print(f"DEBUG: Handling dict format")
                summarized = {}
                
                # Handle common dictionary structures in fantasy APIs
                # Case 1: Position-keyed dictionary (e.g., {"QB": [...], "RB": [...], ...})
                if any(pos in rankings_data for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]):
                    print(f"DEBUG: Case 1 - Position-keyed dictionary detected")
                    for position, players in rankings_data.items():
                        if isinstance(players, list) and players:
                            # For QBs, take more players to allow VORP calculations (need ~25 for replacement level)
                            # For other positions, take more players for better analysis  
                            max_players = 25 if position == "QB" else 15
                            summarized[position] = []
                            for player in players[:max_players]:
                                if isinstance(player, dict):
                                    player_summary = {
                                        "name": player.get("display_name", player.get("name", "")),
                                        "team": player.get("team", ""),
                                        "rank": player.get("rank", player.get("position_rank", 0))
                                    }
                                    
                                    # Include projected points if available (critical for VORP calculations)
                                    if "proj_pts" in player:
                                        player_summary["projected_points"] = player.get("proj_pts", 0)
                                    
                                    summarized[position].append(player_summary)
                                else:
                                    # Handle unexpected player data format
                                    summarized[position].append({"error": "Unexpected player data format"})
                
                # Case 2: Data is in a "data" key
                elif "data" in rankings_data and isinstance(rankings_data["data"], (list, dict)):
                    print(f"DEBUG: Case 2 - Data key detected")
                    return self._summarize_fantasy_rankings(rankings_data["data"])
                      # Case 3: Other dictionary structure - extract key metadata
                else:
                    print(f"DEBUG: Case 3 - Other dictionary structure")
                    summarized = {
                        "metadata": {k: v for k, v in rankings_data.items() if k not in ["players", "data"] and not isinstance(v, (list, dict))},
                        "players_sample": []
                    }
                      # First check for "players" key specifically (common in Fantasy Nerds API)
                    if "players" in rankings_data and isinstance(rankings_data["players"], list):
                        print(f"DEBUG: Found 'players' key with {len(rankings_data['players'])} players")
                        # Take more players for better VORP analysis
                        summarized["players_sample"] = self._summarize_fantasy_rankings(rankings_data["players"][:30])
                    else:
                        # Try to find player data in any list field
                        for key, value in rankings_data.items():
                            if isinstance(value, list) and value and isinstance(value[0], dict):
                                print(f"DEBUG: Found player data in '{key}' field with {len(value)} items")                                # Take more data for better analysis
                                summarized["players_sample"] = self._summarize_fantasy_rankings(value[:30])
                                break
                        return summarized
            else:
                # Unknown format
                return {"summary": "Rankings data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing fantasy rankings: {e}")
            return {"summary": "Rankings data available but could not be summarized", "error": str(e)}

    def _summarize_news_data(self, news_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Summarize news data (could be a list of articles or a dict with metadata)
        """
        try:
            if isinstance(news_data, list):
                # Take only the first 5 news articles to limit context size
                top_articles = news_data[:5]
                summarized = []
                
                for article in top_articles:
                    if not isinstance(article, dict):
                        continue
                        
                    article_summary = {
                        "headline": article.get("article_headline", ""),
                        "date": article.get("article_date", ""),
                        "author": article.get("article_author", ""),
                        "excerpt": article.get("article_excerpt", "")[:200] + "..." if len(article.get("article_excerpt", "")) > 200 else article.get("article_excerpt", ""),
                        "teams": article.get("teams", [])
                    }
                    summarized.append(article_summary)
                
                return summarized
            else:
                # If it's a dict, return a summary
                if isinstance(news_data, dict):                    # Handle dict format (if news data is wrapped in a dict)
                    articles_count = len(news_data.get("articles", [])) if "articles" in news_data else len(news_data)
                    return {"summary": "News data available", "count": articles_count}
                else:
                    return {"summary": "News data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing news data: {e}")
            return {"summary": "News data available but could not be summarized", "error": str(e)}

    def _summarize_ros_projections(self, ros_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize ROS (Rest of Season) projections data specifically
        ROS data typically has structure: {"season": 2025, "projections": {"QB": [...], "RB": [...], ...}}
        """
        if not ros_data:
            return {"summary": "No ROS projections data available"}
            
        try:
            # Handle if the data is a list directly (some Fantasy Nerds endpoints return lists)
            if isinstance(ros_data, list):
                # If it's a list, treat it as fantasy rankings
                return self._summarize_fantasy_rankings(ros_data)
            else:
                # Handle dictionary format
                summarized = {
                    "season": ros_data.get("season", ""),
                    "metadata": {k: v for k, v in ros_data.items() if k not in ["projections", "season"] and not isinstance(v, dict)}
                }
                  # Handle the main projections data
                if "projections" in ros_data and isinstance(ros_data["projections"], dict):
                    projections = ros_data["projections"]
                    
                    # Summarize each position's projections
                    for position, players in projections.items():
                        if isinstance(players, list) and players:
                            # For VORP calculations, we need more QBs to see replacement level (typically QB20-24)
                            # For other positions, still take more for better analysis
                            max_players = 30 if position == "QB" else 20
                            
                            position_summary = []
                            for player in players[:max_players]:
                                if isinstance(player, dict):
                                    player_summary = {
                                        "name": player.get("name", ""),
                                        "team": player.get("team", ""),
                                        "position": player.get("position", position)
                                    }
                                    
                                    # Include projected points (critical for VORP calculations)
                                    if "proj_pts" in player:
                                        player_summary["projected_points"] = player.get("proj_pts", 0)
                                    
                                    # Include other key stats that might be useful
                                    for stat in ["passing_yards", "passing_touchdowns", "rushing_yards", "rushing_touchdowns", "receiving_yards", "receiving_touchdowns"]:
                                        if stat in player:
                                            player_summary[stat] = player.get(stat, 0)
                                            
                                    position_summary.append(player_summary)
                            
                            summarized[position] = position_summary
                            
                else:
                    # Fallback: treat the entire ROS data as fantasy rankings
                    return self._summarize_fantasy_rankings(ros_data)
                    
                return summarized
            
        except Exception as e:
            print(f"Error summarizing ROS projections: {e}")
            return {"summary": "ROS projections data available but could not be summarized", "error": str(e)}

    def _summarize_players_data(self, players_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize players data from the players endpoint
        """
        try:
            if isinstance(players_data, list):
                # If it's a list of players directly
                summarized = {
                    "players_count": len(players_data),
                    "sample_players": []
                }
                
                # Take a sample of players (limit to 20 for context size)
                for player in players_data[:20]:
                    if isinstance(player, dict):
                        player_summary = {
                            "name": player.get("display_name", player.get("name", "")),
                            "team": player.get("team", ""),
                            "position": player.get("position", ""),
                            "jersey_number": player.get("jersey", ""),
                            "status": player.get("status", "")
                        }
                        summarized["sample_players"].append(player_summary)
                
                return summarized
            else:
                # If it's a dictionary structure
                if "players" in players_data:
                    return self._summarize_players_data(players_data["players"])
                else:
                    return {"summary": "Players data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing players data: {e}")
            return {"summary": "Players data available but could not be summarized", "error": str(e)}

    def _summarize_depth_charts(self, depth_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize depth chart data
        """
        print(f"DEBUG: _summarize_depth_charts called with data type: {type(depth_data)}")
        
        try:
            if isinstance(depth_data, list):
                print(f"DEBUG: Processing list format with {len(depth_data)} teams")
                # If it's a list of teams
                summarized = {
                    "teams_count": len(depth_data),
                    "teams": []
                }
                
                for i, team in enumerate(depth_data[:5]):  # Limit to 5 teams
                    print(f"DEBUG: Processing team {i}: {list(team.keys()) if isinstance(team, dict) else type(team)}")
                    if isinstance(team, dict):
                        team_summary = {
                            "team": team.get("team", team.get("name", team.get("alias", ""))),
                            "positions": {}
                        }
                        
                        # Check if this is Detroit Lions
                        team_identifier = team.get("team", team.get("name", team.get("alias", ""))).lower()
                        if "detroit" in team_identifier or "lions" in team_identifier:
                            print(f"DEBUG: Found Detroit Lions team data: {team}")
                        
                        # Sample a few positions
                        for key, value in team.items():
                            if key not in ["team", "name", "alias", "id"] and isinstance(value, list):
                                team_summary["positions"][key] = []
                                for player in value[:3]:  # Top 3 players per position
                                    if isinstance(player, dict):
                                        team_summary["positions"][key].append(player.get("name", ""))
                                    else:
                                        team_summary["positions"][key].append(str(player))
                        
                        summarized["teams"].append(team_summary)
                
                return summarized
                
            elif isinstance(depth_data, dict):
                print(f"DEBUG: Processing dict format with keys: {list(depth_data.keys())}")
                summarized = {
                    "teams_count": 0,
                    "teams": []
                }
                
                # Handle different dictionary structures
                # Case 1: Teams as keys (e.g., {"DET": {...}, "GB": {...}})
                if any(len(key) <= 3 and key.isupper() for key in depth_data.keys()):
                    print("DEBUG: Case 1 - Team abbreviations as keys")
                    for team_abbr, team_depth in depth_data.items():
                        if "DET" in team_abbr.upper() or "DETROIT" in team_abbr.upper():
                            print(f"DEBUG: Found Detroit Lions depth data under key '{team_abbr}': {team_depth}")
                        
                        if isinstance(team_depth, dict):
                            team_summary = {
                                "team": team_abbr,
                                "positions": {}
                            }
                            
                            for position, players in team_depth.items():
                                if isinstance(players, list):
                                    team_summary["positions"][position] = []
                                    for player in players[:3]:  # Top 3 players
                                        if isinstance(player, dict):
                                            team_summary["positions"][position].append(player.get("name", ""))
                                        else:
                                            team_summary["positions"][position].append(str(player))
                            
                            summarized["teams"].append(team_summary)
                            summarized["teams_count"] += 1
                  # Case 2: Check for "teams" key
                elif "teams" in depth_data:
                    print("DEBUG: Case 2 - Teams under 'teams' key")
                    return self._summarize_depth_charts(depth_data["teams"])
                
                # Case 2.5: Check for "charts" key (Fantasy Nerds API specific)
                elif "charts" in depth_data:
                    print("DEBUG: Case 2.5 - Charts under 'charts' key")
                    return self._summarize_depth_charts(depth_data["charts"])
                
                # Case 3: Other structure - try to find team data
                else:
                    print("DEBUG: Case 3 - Other structure, searching for team data")
                    for key, value in depth_data.items():
                        if isinstance(value, (list, dict)) and key.lower() not in ["metadata", "status", "error"]:
                            print(f"DEBUG: Found potential team data under key '{key}': {type(value)}")
                            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                                # Looks like a list of teams
                                return self._summarize_depth_charts(value)
                            elif isinstance(value, dict):
                                # Might be a single team or nested structure
                                team_summary = {
                                    "team": key,
                                    "positions": {}
                                }
                                
                                for pos_key, pos_value in value.items():
                                    if isinstance(pos_value, list):
                                        team_summary["positions"][pos_key] = []
                                        for player in pos_value[:3]:
                                            if isinstance(player, dict):
                                                team_summary["positions"][pos_key].append(player.get("name", ""))
                                            else:
                                                team_summary["positions"][pos_key].append(str(player))
                                
                                if team_summary["positions"]:  # Only add if we found positions
                                    summarized["teams"].append(team_summary)
                                    summarized["teams_count"] += 1
                
                return summarized
                
            else:
                print(f"DEBUG: Unexpected data format: {type(depth_data)}")
                return {"summary": "Depth chart data available but in unexpected format", "debug_type": str(type(depth_data))}
                
        except Exception as e:
            print(f"Error summarizing depth chart data: {e}")
            import traceback
            traceback.print_exc()
            return {"summary": "Depth chart data available but could not be summarized", "error": str(e)}

    def _summarize_bye_weeks(self, bye_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize bye weeks data
        """
        try:
            if isinstance(bye_data, list):
                summarized = {
                    "bye_weeks": []
                }
                
                for week_data in bye_data:
                    if isinstance(week_data, dict):
                        summarized["bye_weeks"].append({
                            "week": week_data.get("week", ""),
                            "teams": week_data.get("teams", [])
                        })
                
                return summarized
            elif isinstance(bye_data, dict):
                if "weeks" in bye_data:
                    return self._summarize_bye_weeks(bye_data["weeks"])
                else:
                    return {"summary": "Bye weeks data available", "data": bye_data}
            else:
                return {"summary": "Bye weeks data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing bye weeks data: {e}")
            return {"summary": "Bye weeks data available but could not be summarized", "error": str(e)}

    def _summarize_add_drops(self, add_drops_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize add/drops data
        """
        try:
            if isinstance(add_drops_data, list):
                summarized = {
                    "total_transactions": len(add_drops_data),
                    "top_adds": [],
                    "top_drops": []
                }
                
                # Separate adds and drops
                for transaction in add_drops_data[:10]:  # Limit to 10
                    if isinstance(transaction, dict):
                        if transaction.get("type") == "add":
                            summarized["top_adds"].append({
                                "player": transaction.get("player", ""),
                                "team": transaction.get("team", ""),
                                "position": transaction.get("position", ""),
                                "percentage": transaction.get("percentage", 0)
                            })
                        elif transaction.get("type") == "drop":
                            summarized["top_drops"].append({
                                "player": transaction.get("player", ""),
                                "team": transaction.get("team", ""),
                                "position": transaction.get("position", ""),
                                "percentage": transaction.get("percentage", 0)
                            })
                
                return summarized
            else:
                return {"summary": "Add/drops data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing add/drops data: {e}")
            return {"summary": "Add/drops data available but could not be summarized", "error": str(e)}

    def _summarize_weather_data(self, weather_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize weather forecast data
        """
        try:
            if isinstance(weather_data, list):
                summarized = {
                    "games_count": len(weather_data),
                    "forecasts": []
                }
                
                for game in weather_data[:5]:  # Limit to 5 games
                    if isinstance(game, dict):
                        summarized["forecasts"].append({
                            "game": f"{game.get('away_team', '')} @ {game.get('home_team', '')}",
                            "temperature": game.get("temperature", ""),
                            "conditions": game.get("conditions", ""),
                            "wind": game.get("wind", ""),
                            "precipitation": game.get("precipitation", "")
                        })
                
                return summarized
            else:
                return {"summary": "Weather data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing weather data: {e}")
            return {"summary": "Weather data available but could not be summarized", "error": str(e)}

    def _summarize_dfs_data(self, dfs_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize DFS (Daily Fantasy Sports) data
        """
        try:
            if isinstance(dfs_data, list):
                summarized = {
                    "players_count": len(dfs_data),
                    "top_value_players": []
                }
                
                # Sort by value and take top players
                sorted_players = sorted(dfs_data, key=lambda x: x.get("value", 0), reverse=True)
                
                for player in sorted_players[:10]:  # Top 10 value players
                    if isinstance(player, dict):
                        summarized["top_value_players"].append({
                            "player": player.get("name", ""),
                            "team": player.get("team", ""),
                            "position": player.get("position", ""),
                            "salary": player.get("salary", 0),
                            "projected_points": player.get("projected_points", 0),
                            "value": player.get("value", 0)
                        })
                
                return summarized
            else:
                return {"summary": "DFS data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing DFS data: {e}")
            return {"summary": "DFS data available but could not be summarized", "error": str(e)}

    def _summarize_dfs_slates(self, slates_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize DFS slates data
        """
        try:
            if isinstance(slates_data, list):
                summarized = {
                    "slates_count": len(slates_data),
                    "available_slates": []
                }
                
                for slate in slates_data:
                    if isinstance(slate, dict):
                        summarized["available_slates"].append({
                            "slate_id": slate.get("slate_id", ""),
                            "name": slate.get("name", ""),
                            "start_time": slate.get("start_time", ""),
                            "games_count": len(slate.get("games", []))
                        })
                
                return summarized
            else:
                return {"summary": "DFS slates data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing DFS slates data: {e}")
            return {"summary": "DFS slates data available but could not be summarized", "error": str(e)}

    def _summarize_nfl_picks(self, picks_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize NFL picks data
        """
        try:
            if isinstance(picks_data, list):
                summarized = {
                    "games_count": len(picks_data),
                    "picks": []
                }
                
                for game in picks_data:
                    if isinstance(game, dict):
                        summarized["picks"].append({
                            "game": f"{game.get('away_team', '')} @ {game.get('home_team', '')}",
                            "spread": game.get("spread", ""),
                            "over_under": game.get("over_under", ""),
                            "expert_picks": game.get("expert_picks", [])[:3]  # Limit to 3 expert picks
                        })
                
                return summarized
            else:
                return {"summary": "NFL picks data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing NFL picks data: {e}")
            return {"summary": "NFL picks data available but could not be summarized", "error": str(e)}

    def _summarize_draft_projections(self, projections_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize draft projections data which has a specific structure with position-based arrays
        """
        try:
            print(f"DEBUG: _summarize_draft_projections called with data type: {type(projections_data)}")
            
            if not projections_data:
                return {"summary": "No draft projections data available"}
            
            # Handle the projections structure: {projections: {QB: [...], RB: [...], etc}, season: 2025}
            if "projections" in projections_data:
                projections = projections_data["projections"]
                season = projections_data.get("season", "Unknown")
                
                summarized = {
                    "season": season,
                    "positions": {}
                }
                
                # Process each position
                for position, players in projections.items():
                    if isinstance(players, list) and players:
                        # Take top players from each position (limit to avoid context overflow)
                        top_players = players[:15]  # Top 15 per position
                        position_summary = []
                        
                        for rank, player in enumerate(top_players, 1):
                            if isinstance(player, dict):
                                player_summary = {
                                    "rank": rank,
                                    "name": player.get("name", ""),
                                    "team": player.get("team", ""),
                                    "position": player.get("position", position),
                                    "player_id": player.get("playerId", "")
                                }
                                
                                # Include key projection stats based on position
                                if position == "QB":
                                    player_summary["projections"] = {
                                        "passing_yards": player.get("passing_yards", ""),
                                        "passing_touchdowns": player.get("passing_touchdowns", ""),
                                        "rushing_yards": player.get("rushing_yards", ""),
                                        "rushing_touchdowns": player.get("rushing_touchdowns", "")
                                    }
                                elif position in ["RB", "WR", "TE"]:
                                    player_summary["projections"] = {
                                        "rushing_yards": player.get("rushing_yards", ""),
                                        "rushing_touchdowns": player.get("rushing_touchdowns", ""),
                                        "receiving_yards": player.get("receiving_yards", ""),
                                        "receiving_touchdowns": player.get("receiving_touchdowns", ""),
                                        "receptions": player.get("receptions", "")
                                    }
                                
                                position_summary.append(player_summary)
                        
                        summarized["positions"][position] = {
                            "count": len(players),
                            "top_players": position_summary
                        }
                
                return summarized
            else:
                # Fallback to regular rankings processing if structure is different
                return self._summarize_fantasy_rankings(projections_data)
                
        except Exception as e:
            print(f"Error summarizing draft projections: {e}")
            return {"summary": "Draft projections data available but could not be summarized", "error": str(e)}

llm_service = LLMService()
