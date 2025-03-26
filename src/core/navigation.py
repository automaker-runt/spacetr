import heapq, math
import pandas as pd
from typing import Dict, List, Tuple, Union

from core.utils.coord import GameCoord, distance
from core.utils.objmanager import ObjManager
from core.utils.dfop import traits_lookup
from hkeep.log.logger import get_logger


class NavItem:
	"""
	Represents a navigation item with 
	- total_cost
	- current fuel
	- current waypoint/coordinates
	- path
	- cumulative refuel cost
	"""
	
	def __init__(self, total_cost:int, curr_fuel:int, curr_coord:GameCoord, path: List[Dict], fuel_cost:int):
		self.total_cost = total_cost
		self.curr_fuel = curr_fuel
		self.curr_coord = curr_coord
		self.path = path
		self.fuel_cost = fuel_cost

		self.no_fuel_prices = True

	def __lt__(self, other):
		return self.total_cost < other.total_cost
	
	def decompress(self):
		return self.total_cost, self.curr_fuel, self.curr_coord, self.path, self.fuel_cost


class Navigation:
	"""
	Navigation class that handles route planning and optimization using Dijkstra's algorithm.
	"""
	_log = get_logger(__name__)
	posted_default_fuel_price = False
	hop_default_weight = 1000
	drift_max_weight = 1000000
	drift_default_weight = 100000
	drift_reduced_weight = 2500

	def __init__(self, Objman: ObjManager, df_sys_wps: pd.DataFrame, market_df: pd.DataFrame):
		"""
		Initialize the Navigation class with object manager and waypoint data.
		
		Args:
			Objman: Object manager with access to database and config
			df_sys_wps: DataFrame containing waypoint information
			market_df: DataFrame containing market data (fuel prices)
		"""
		self.Objman = Objman
		self.df_sys_wps = df_sys_wps
		self.market_df = market_df
		self.config = Objman.Conf.config
		
		# Filter waypoints with MARKETPLACE trait for refueling
		self.marketplace_waypoints = self._get_marketplace_waypoints()

	def _get_marketplace_waypoints(self) -> List[str]:
		"""
		Extract waypoints that have the MARKETPLACE trait for refueling.
		
		Returns:
			List of waypoint symbols that have marketplaces
		"""
		if self.df_sys_wps is None or self.df_sys_wps.empty or "traits" not in self.df_sys_wps.columns:
			self._log.warning("Cannot determine marketplace waypoints - missing data")
			return []
		
		# Use traits_lookup to find waypoints with MARKETPLACE trait
		marketplace_df = traits_lookup(self.df_sys_wps, ["MARKETPLACE"])
		
		if marketplace_df.empty:
			self._log.warning("No waypoints with MARKETPLACE trait found for refueling")
			return []
			
		# Extract waypoint symbols
		return marketplace_df["wp_symbol"].tolist() if "wp_symbol" in marketplace_df.columns else []

	def optimize_route(self, 
					  start_coord: GameCoord, 
					  target_coord: GameCoord, 
					  current_fuel: int, 
					  fuel_capacity: int,
					  flight_mode: str = "CRUISE") -> Tuple[List[Dict], int]:
		"""
		Find the optimal route between two coordinates using Dijkstra's algorithm.
		
		Args:
			start_coord: Starting GameCoord
			target_coord: Target GameCoord
			current_fuel: Current fuel amount
			fuel_capacity: Maximum fuel capacity
			flight_mode: Flight mode for navigation ("CRUISE", "BURN", "DRIFT", "STEALTH")
			
		Returns:
			Tuple containing:
			- List of waypoints forming the path with refueling info
			- Estimated total cost of the path
		"""
		# If start and target are the same, return empty path
		if start_coord.wp == target_coord.wp:
			return [], 0
		
		# If MINIMIZE_NAVIGATION_REQUESTS is True, return direct path in DRIFT mode
		elif self.config.get("MINIMIZE_NAVIGATION_REQUESTS", False) and current_fuel >= 2:
			self._log.debug("MINIMIZE_NAVIGATION_REQUESTS is True, returning direct path in DRIFT mode")
			
			# Calculate fuel cost for direct path
			total_cost = self.drift_default_weight + self._calculate_fuel_cost(start_coord, target_coord, "DRIFT")
			
			# Create a simple path with one hop
			path = [{
				"coord": target_coord,
				"refuel": False,
				"refuel_amount": 0,
				"mode": "DRIFT"
			}]
			
			return path, total_cost, 0
		
		# Otherwise, use Dijkstra algorithm to find optimal path
		self._log.debug(f"Finding optimal path from {start_coord.wp} to {target_coord.wp} with {current_fuel} fuel and {fuel_capacity} capacity, distance: {distance(start_coord, target_coord)}")
		path, total_cost, refuel_cost = self._find_optimal_path(start_coord, target_coord, current_fuel, fuel_capacity, flight_mode)
		# cleans path from duplicates indicating refueling at the same waypoint
		path_items_to_remove = []
		# merge refueling instruction in to first item of the pair
		for indx in range(len(path)):
			if path[indx]["refuel"] and path[indx]["coord"].wp == path[indx-1]["coord"].wp:
				path[indx-1]["refuel"] = True
				path[indx-1]["refuel_amount"] = path[indx]["refuel_amount"]
				path_items_to_remove.append(path[indx].copy())
		# remove duplicate waypoint items
		for item in path_items_to_remove:
			path.remove(item)
		
		return path, total_cost, refuel_cost
	
	def _find_optimal_path(self, 
						  start_coord: GameCoord, 
						  target_coord: GameCoord, 
						  current_fuel: int, 
						  fuel_capacity: int,
						  flight_mode: str) -> Tuple[List[Dict], int]:
		"""
		Implement Dijkstra's algorithm to find the optimal path.
		
		Args:
			start_coord: Starting GameCoord
			target_coord: Target GameCoord
			current_fuel: Current fuel amount
			fuel_capacity: Maximum fuel capacity
			flight_mode: Flight mode for navigation
			
		Returns:
			Tuple containing:
			- List of waypoints forming the path with refueling info
			- Estimated total cost of the path
		"""
		# Initialize data structures for Dijkstra's algorithm
		pq = []  # Priority queue
		costs = {}  # Dictionary to store costs to each node
		fuel_levels = {}  # Dictionary to track fuel levels at each waypoint

		# Start with the starting coordinate
		initial_fuel_cost = 0
		start_item = NavItem(0, current_fuel, start_coord, [], initial_fuel_cost)
		heapq.heappush(pq, start_item)
		costs[start_coord.wp] = 0
		fuel_levels[start_coord.wp] = current_fuel
		
		# Extract valid waypoints as nodes for our graph
		valid_waypoints = self._get_valid_waypoints()
		
		while pq:
			# Get the next item with lowest total cost from the priority queue
			nav_item = heapq.heappop(pq)
			total_cost, current_fuel_level, current_wp, path_so_far, cum_refuel_cost = nav_item.decompress()
			
			# If we've reached the target, reconstruct and return the path
			if current_wp.wp == target_coord.wp:
				""" heapq.heappush(target_paths, nav_item)
				continue """
				return path_so_far, total_cost, cum_refuel_cost
			
			# Skip if we've already found a better path to this waypoint
			if current_wp.wp in costs and total_cost > costs[current_wp.wp]:
				continue
			
			# Look at all possible neighbors
			for _, neighbor_wp in valid_waypoints.iterrows():
				neighbor_coord = neighbor_wp.GmCrd
				
				# Skip if same waypoint
				if neighbor_coord.wp == current_wp.wp:
					continue
				
				# Skip if not in the same system
				if neighbor_coord.sys != current_wp.sys:
					continue
				
				# Calculate the cost to move to this neighbor
				fuel_cost = self._calculate_fuel_cost(current_wp, neighbor_coord, flight_mode)

				# distance to neighbor is the fuel cost to move to the neighbor
				distance_to_neighbor = fuel_cost if flight_mode in ("CRUISE", "STEALTH") else self._calculate_fuel_cost(current_wp, neighbor_coord, "CRUISE")
				
				# Check if we have enough fuel to reach this waypoint
				if fuel_cost > current_fuel_level:
					# We need to refuel, but check if current waypoint has a marketplace
		 			# Also check if neighbor_coord is reachable within fuel_capacity
					if (current_wp.wp not in self.marketplace_waypoints or
						fuel_cost > fuel_capacity):
						# need to implement case where we have more fuel in cargo/inventory
						
						new_fuel_level = current_fuel_level - 1
						
						# discard this path if next waypoint is not marketplace and we have there no fuel left
						if new_fuel_level <= 0 and neighbor_coord.wp not in self.marketplace_waypoints:
							continue

						# go by "DRIFT" mode
						if ((neighbor_coord.coord == target_coord.coord and distance_to_neighbor <= fuel_capacity) or
		  					(len(path_so_far) > 0 and path_so_far[-1]["mode"] == "DRIFT") or
		  					(len(path_so_far) == 0 and neighbor_coord.wp not in self.marketplace_waypoints)):
							drift_hop_cost = round(self.drift_max_weight * distance_to_neighbor/100)
						elif neighbor_coord.wp not in self.marketplace_waypoints:
							drift_hop_cost = round(self.drift_default_weight * distance_to_neighbor/100)
						else:
							drift_hop_cost = round(self.drift_reduced_weight * distance_to_neighbor/100)
						
						""" if neighbor_coord.wp in ("X1-CR27-J85", "X1-CR27-FZ5D", "X1-CR27-A1"):
							print(neighbor_coord.wp, distance_to_neighbor, drift_hop_cost) """
						
						new_cost = total_cost + drift_hop_cost + 1

						# Check if this path is better than previously found paths
						if (neighbor_coord.wp not in costs or 
							new_cost < costs[neighbor_coord.wp] or 
							(new_cost == costs[neighbor_coord.wp] and new_fuel_level > fuel_levels.get(neighbor_coord.wp, 0))):
							
							# Update costs and fuel levels
							costs[neighbor_coord.wp] = new_cost
							fuel_levels[neighbor_coord.wp] = new_fuel_level
							
							# Create updated path with refueling
							new_path = path_so_far + [{
								"coord": neighbor_coord,
								"refuel": False,
								"refuel_amount": 0,
								"mode": "DRIFT"
							}]

							""" self.print_path(new_path, new_cost, new_fuel_level, cum_refuel_cost) """
							# Add to priority queue using NavItem
							new_nav_item = NavItem(new_cost, new_fuel_level, neighbor_coord, new_path, cum_refuel_cost)
							heapq.heappush(pq, new_nav_item)
								
					else:
						# We can refuel at this waypoint
						refuel_amount = min(fuel_capacity - current_fuel_level, fuel_capacity)
						refuel_cost = self._calculate_refuel_cost(current_wp, refuel_amount)
						
						# New fuel level after refueling
						new_fuel_level = current_fuel_level + refuel_amount - fuel_cost
						
						# New cost including refueling
						# 1000 per non-DRIFT hop
						new_cost = total_cost + self.hop_default_weight + fuel_cost + refuel_cost
						
						# Check if this path is better than previously found paths
						if (neighbor_coord.wp not in costs or 
							new_cost < costs[neighbor_coord.wp] or 
							(new_cost == costs[neighbor_coord.wp] and new_fuel_level > fuel_levels.get(neighbor_coord.wp, 0))):
							
							# Update costs and fuel levels
							costs[neighbor_coord.wp] = new_cost
							fuel_levels[neighbor_coord.wp] = new_fuel_level
							
							# Create updated path with refueling
							new_path = path_so_far + [{
								"coord": current_wp,
								"refuel": True,
								"refuel_amount": refuel_amount,
								"mode": flight_mode
							}, {
								"coord": neighbor_coord,
								"refuel": False,
								"refuel_amount": 0,
								"mode": flight_mode
							}]
							
							""" self.print_path(new_path, new_cost, new_fuel_level, cum_refuel_cost) """
							
							# Add to priority queue using NavItem
							new_nav_item = NavItem(new_cost, new_fuel_level, neighbor_coord, new_path, cum_refuel_cost+refuel_cost)
							heapq.heappush(pq, new_nav_item)
				
				else:
					# We have enough fuel to reach this waypoint without refueling
					new_fuel_level = current_fuel_level - fuel_cost
					# 1000 per non-DRIFT hop
					new_cost = total_cost + self.hop_default_weight + fuel_cost
					
					# Check if this path is better than previously found paths
					if (neighbor_coord.wp not in costs or 
						new_cost < costs[neighbor_coord.wp] or 
						(new_cost == costs[neighbor_coord.wp] and new_fuel_level > fuel_levels.get(neighbor_coord.wp, 0))):
						
						# Update costs and fuel levels
						costs[neighbor_coord.wp] = new_cost
						fuel_levels[neighbor_coord.wp] = new_fuel_level
						
						# Create updated path
						new_path = path_so_far + [{
							"coord": neighbor_coord,
							"refuel": False,
							"refuel_amount": 0,
							"mode": flight_mode
						}]
						
						# Add to priority queue using NavItem
						new_nav_item = NavItem(new_cost, new_fuel_level, neighbor_coord, new_path, cum_refuel_cost)
						heapq.heappush(pq, new_nav_item)
		
		# If we've exhausted all possible paths and haven't found the target
		self._log.debug(f"Could not find a path from {start_coord.wp} to {target_coord.wp}")
		return [], float('inf'), float('inf')
	
	def _calculate_fuel_cost(self, start: GameCoord, end: GameCoord, mode: str) -> int:
		"""
		Calculate the fuel cost for a hop between two waypoints.
		
		Args:
			start: Starting GameCoord
			end: Ending GameCoord
			mode: Flight mode
			
		Returns:
			Fuel cost as integer
		"""
		dist = distance(start, end)
		
		if mode in ("CRUISE", "STEALTH"):
			return round(dist)
		elif mode == "DRIFT":
			return 1
		elif mode == "BURN":
			amt = 2 * round(dist)
			return max(2, amt)
		
		# Default case
		return round(dist)
	
	def _calculate_refuel_cost(self, waypoint: GameCoord, amount: int) -> int:
		"""
		Calculate the cost to refuel at a waypoint.
		
		Args:
			waypoint: GameCoord of the waypoint to refuel at
			amount: Amount of fuel to buy
			
		Returns:
			Cost to refuel
		"""
		# Get fuel price from market data
		fuel_price = self._get_fuel_price(waypoint)
		
		# Calculate total cost
		return math.ceil(amount/100) * fuel_price
	
	def _get_fuel_price(self, waypoint: GameCoord) -> int:
		"""
		Get the fuel price at a specific waypoint.
		
		Args:
			waypoint: GameCoord of the waypoint
			
		Returns:
			Fuel price:
			- If available, the actual price at the waypoint
			- If not available at this waypoint but available in system, mean of system prices
			- If no prices in system, defaults to 190
		"""
		# Try to find fuel price in market data
		if self.market_df is not None and not self.market_df.empty:
			# Filter market data for FUEL and the specific waypoint
			fuel_data = self.market_df[
				(self.market_df['good'] == 'FUEL') & 
				(self.market_df['waypoint'] == waypoint.wp)
			]
			
			if not fuel_data.empty:
				# Return the purchase price (sell side)
				sell_data = fuel_data[fuel_data['side'] == 'SELL']
				if not sell_data.empty:
					return sell_data['price'].values[0]
			
			# If no price found for this waypoint, try to get mean price from the system
			system_fuel_data = self.market_df[
				(self.market_df['good'] == 'FUEL') & 
				(self.market_df['waypoint'].str.startswith(waypoint.sys)) &
				(self.market_df['side'] == 'SELL')
			]
			
			if not system_fuel_data.empty:
				mean_price = int(system_fuel_data['price'].mean())
				self._log.debug(f"Using mean fuel price of {mean_price} for waypoint {waypoint.wp}")
				return mean_price
		
		# Default fuel price if no system fuel prices are available
		if not self.posted_default_fuel_price:
			self._log.warning(f"No fuel prices found in system {waypoint.sys}, using default price of 190")
			self.posted_default_fuel_price = True
		return 190
	
	def _get_valid_waypoints(self) -> pd.DataFrame:
		"""
		Get valid waypoints from the DataFrame.
		
		Returns:
			DataFrame containing valid waypoints for pathfinding
		"""
		if self.df_sys_wps is None or self.df_sys_wps.empty:
			self._log.warning("No waypoints found in DataFrame, returning empty DataFrame")
			return pd.DataFrame()
		
		# Filter waypoints that can be used for navigation
		# This would typically include stations, jump gates, etc.
		# For now, we're using all waypoints in the DataFrame
		return self.df_sys_wps
	
	
	def print_path(self, path: List[Dict], new_cost: int, new_fuel_level: int, cum_refuel_cost: int) -> None:
		"""
		Print the path in a readable format
		"""
		s = str()
		for i in path:
			ss = list(str(v) for v in i.values())
			s += f' {ss}'
		print(s, f'{new_cost} {new_fuel_level} {cum_refuel_cost}', "#################")
