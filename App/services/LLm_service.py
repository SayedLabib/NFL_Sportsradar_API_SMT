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
            "PRIORITIZE using the Fantasy Nerds API data whenever available also using your own reasoning but you may use your detail visual and reasoning when appropriate. "
            "Response strategy:\n"
            "1. FIRST PRIORITY: Use the Fantasy Nerds data when available - cite specific statistics, rankings, and metrics from this data\n"
            "2. SECOND PRIORITY: When Fantasy Nerds data is limited or doesn't contain information requested:\n"
            "   a. Clearly state that the specific data requested isn't available from Fantasy Nerds\n"
            "   b. Provide own reasoning and knowledge about the topic to give the user helpful information\n"
            "   c. Make it clear which parts of your answer are from Fantasy Nerds data vs. general knowledge\n"
            "3. Identify trends and insights that are directly observable in the data\n"
            "4. Make logical inferences that are clearly supported by the available data\n"
            "5. For player-specific queries, if the player isn't found in Fantasy Nerds data, provide general information about the player\n"
            "6. For fantasy advice queries, prioritize Fantasy Nerds data but supplement with general strategy knowledge when helpful\n"
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
                "The following NFL data is the ONLY data you should use to answer the user's query. "
                "Do not rely on your general knowledge about the NFL or fantasy football. "
                "If information is not present in this data, clearly state that it's not available in the provided Fantasy Nerds data. "
                "When the data contains multiple types of information (like standings, schedules, player info), "
                "integrate them for a comprehensive analysis, but do not add information beyond what's provided. "
                "For any rankings or statistics, cite specific numbers and player names exactly as they appear in the data. "
                "IMPORTANT: When discussing player rankings, explicitly name the players from the data with their exact ranks, teams, and other available details. "
                "Do not use placeholders like [Player Name]. When answering questions about specific players, extract their information from the draft_rankings or weekly_rankings sections. "
                "If you can't find a specific player in the data, state that clearly."
            )
            
            messages.append({"role": "system", "content": data_instructions})
            
            # Format and add the summarized context data
            context_str = f"{json.dumps(summarized_data, indent=2)}"
            # Limit context string to avoid payload too large - reduced for GPT's token limit
            if len(context_str) > 15000:  # Reduced size for GPT's token limit
                context_str = context_str[:15000] + "...[additional data truncated for size]"
                
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
        handling combined data from multiple endpoints
        """
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
                
            return summarized
        except Exception as e:
            print(f"Error during data summarization: {e}")
            return {"summary": "Data available but could not be summarized due to an error",
                    "error": str(e)}

    def _summarize_league_structure(self, league_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize league structure data"""
        if not league_data:
            return {}
            
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
            # Take up to 5 games to avoid overloading context
            for game in games_data[:5]:
                game_summary = {
                    "id": game.get("id", ""),
                    "status": game.get("status", ""),
                    "scheduled": game.get("scheduled", ""),
                    "home_team": {
                        "name": game.get("home", {}).get("name", ""),
                        "alias": game.get("home", {}).get("alias", ""),
                        "points": game.get("home_points", None)
                    },
                    "away_team": {
                        "name": game.get("away", {}).get("name", ""),
                        "alias": game.get("away", {}).get("alias", ""),
                        "points": game.get("away_points", None)
                    }
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
                                "win_pct": team.get("win_pct", 0),
                                "points_for": team.get("points_for", 0),
                                "points_against": team.get("points_against", 0)
                            })
                        
                        conf_summary["divisions"].append(div_summary)
                    
                    summary["conferences"].append(conf_summary)
            
            return summary
        except Exception as e:
            print(f"Error summarizing standings: {e}")
            return {"summary": "Standings data available but could not be summarized"}
    
    def _summarize_schedule_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize schedule data to essential games info"""
        summarized = {
            "year": data.get("year", ""),
            "type": data.get("type", ""),
            "games": []
        }
        
        try:
            # Take only the first 10 games to limit size
            games = data.get("games", [])[:10]
            for game in games:
                game_summary = {
                    "id": game.get("id", ""),
                    "status": game.get("status", ""),
                    "scheduled": game.get("scheduled", ""),
                    "home_team": {
                        "name": game.get("home", {}).get("name", ""),
                        "alias": game.get("home", {}).get("alias", "")
                    },
                    "away_team": {
                        "name": game.get("away", {}).get("name", ""),
                        "alias": game.get("away", {}).get("alias", "")
                    }
                }
                summarized["games"].append(game_summary)
            
            return summarized
        except Exception as e:
            print(f"Error summarizing schedule data: {e}")
            return {"summary": "Schedule data available but could not be summarized"}

    def _summarize_injury_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize injury report data"""
        summarized = {
            "week": data.get("week", ""),
            "teams_with_injuries": []
        }
        
        try:
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
                    summary[f"{key}_count"] = len(data[key])
                    # Sample a few items if they're dictionaries
                    if data[key] and isinstance(data[key][0], dict):
                        sample_keys = list(data[key][0].keys())[:5]
                        summary[f"{key}_contains"] = sample_keys
        
        return summary

    def _summarize_fantasy_rankings(self, rankings_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Summarize fantasy rankings data (draft rankings or weekly rankings)
        Can handle both list and dictionary responses from the Fantasy Nerds API
        """
        # Debug output to see the raw data
        print("\n=== FANTASY RANKINGS DATA ===")
        print(f"Data type: {type(rankings_data)}")
        if isinstance(rankings_data, list) and rankings_data:
            print(f"First item sample: {rankings_data[0]}")
        elif isinstance(rankings_data, dict) and rankings_data:
            print(f"Keys: {list(rankings_data.keys())}")
        print("============================\n")
            
        if not rankings_data:
            return {"summary": "No rankings data available"}
            
        try:
            # Handle if the response is a list of players
            if isinstance(rankings_data, list):
                # Take only the top 15 players to limit context size
                top_players = rankings_data[:15]
                summarized = []
                
                for player in top_players:
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
                summarized = {}
                
                # Handle common dictionary structures in fantasy APIs
                # Case 1: Position-keyed dictionary (e.g., {"QB": [...], "RB": [...], ...})
                if any(pos in rankings_data for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]):
                    for position, players in rankings_data.items():
                        if isinstance(players, list) and players:
                            # For each position, take top 5 players
                            summarized[position] = []
                            for player in players[:5]:
                                if isinstance(player, dict):
                                    player_summary = {
                                        "name": player.get("display_name", player.get("name", "")),
                                        "team": player.get("team", ""),
                                        "rank": player.get("rank", player.get("position_rank", 0))
                                    }
                                    summarized[position].append(player_summary)
                                else:
                                    # Handle unexpected player data format
                                    summarized[position].append({"error": "Unexpected player data format"})
                
                # Case 2: Data is in a "data" key
                elif "data" in rankings_data and isinstance(rankings_data["data"], (list, dict)):
                    return self._summarize_fantasy_rankings(rankings_data["data"])
                    
                # Case 3: Other dictionary structure - extract key metadata
                else:
                    summarized = {
                        "metadata": {k: v for k, v in rankings_data.items() if k != "players" and not isinstance(v, (list, dict))},
                        "players_sample": []
                    }
                    
                    # Try to find player data in any list field
                    for key, value in rankings_data.items():
                        if isinstance(value, list) and value and isinstance(value[0], dict):
                            summarized["players_sample"] = self._summarize_fantasy_rankings(value[:10])
                            break
                
                return summarized
            else:
                # Unknown format
                return {"summary": "Rankings data available but in unexpected format"}
        except Exception as e:
            print(f"Error summarizing fantasy rankings: {e}")
            return {"summary": "Rankings data available but could not be summarized", "error": str(e)}

llm_service = LLMService()
