# sim_navigation.py
from typing import Dict, List

from core.navigation import Navigation
from core.ships import Ship
from core.utils.coord import GameCoord, distance
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger


class SimulatedShip:
	"""
	A wrapper class to simulate a ship for navigation testing without affecting the actual ship data
	"""
	def __init__(self, ship: Ship, modified_fuel=None, modified_fuel_capacity=None, modified_waypoint=None):
		self.original_ship = ship
		self.name = ship.name
		self.frame = ship.frame
		self.fuel = modified_fuel if modified_fuel is not None else ship.fuel
		self.fuelCapacity = modified_fuel_capacity if modified_fuel_capacity is not None else ship.fuelCapacity
		self.coordinates = ship.coordinates if modified_waypoint is None else modified_waypoint
		self.waypoint = ship.waypoint if modified_waypoint is None else modified_waypoint.wp

	def __str__(self):
		return f"{self.name}.{self.frame.lower()}"

	def in_range(self, target_coord: GameCoord, mode: str = "CRUISE", reserve: float = 0.0) -> bool:
		"""
		Check if the target is in range with current fuel
		"""
		dist = distance(self.coordinates, target_coord)
		
		if mode in ("CRUISE", "STEALTH"):
			fuel_needed = round(dist)
		elif mode == "DRIFT":
			fuel_needed = 1
		elif mode == "BURN":
			amt = 2 * round(dist)
			fuel_needed = max(2, amt)
			
		# Determine reserve amount
		reserve_amount = round(self.fuelCapacity * reserve)
		
		# Return whether hop is in range considering reserve
		return self.fuel >= (fuel_needed + reserve_amount)


class SimulateNavigation:
	"""
	Class to simulate navigation paths without actually moving ships
	"""
	_log = get_logger(__name__)
	
	def __init__(self, session, Conf, SqlHan, Mrkt,
				 events, wake_up_qs, threads):
		"""
		Initialize with the same parameters as Menu
		"""
		self.session = session
		self.Conf = Conf
		self.SqlHan = SqlHan
		self.Objman = ObjManager(session, SqlHan, Conf, None, None)
		self.events = events
		self.wake_up_qs = wake_up_qs
		self.threads = threads
		
		# Data for simulation
		self.ship = None
		self.target_coord = None
		self.flight_mode = "CRUISE"
		self.print_paths = False
		self.df_sys_wps = None
		self.market_df = Mrkt.df
		
	def get_available_ships(self):
		"""
		Get a list of available ships for the simulation
		"""
		from core.shiphandler import ShipHandler
		
		# Create a temporary ship handler to get ships
		ship_handler = ShipHandler(self.Objman, fleet_name="1")
		
		available_ships = []
		for ship_sym, ship in ship_handler.inventory.items():
			available_ships.append(ship)
			
		return available_ships
	
	def get_waypoints_for_system(self, system_symbol):
		"""
		Get all waypoints for a specific system
		"""
		return Waypoint.get_sys_wp_df(self.Objman, system_symbol)
	
	def print_path(self, path: List[Dict], total_cost: int, fuel_level: int, refuel_cost: int) -> None:
		"""Print the path in a readable format"""
		print("\nPath Details:")
		print(f"Total Path Cost: {total_cost}, Remaining Fuel: {fuel_level}, Refuel Cost: {refuel_cost}")
		print("------------------------------------------------------------")
		for idx, step in enumerate(path):
			coord = step["coord"]
			mode = step["mode"]
			refuel = "Yes" if step["refuel"] else "No"
			refuel_amount = step["refuel_amount"] if step["refuel"] else 0
			
			print(f"Step {idx+1}")
			print(f"  - Waypoint: {coord.wp}")
			print(f"  - Coordinates: ({coord.coord[0]}, {coord.coord[1]})")
			print(f"  - Distance: {round(distance(self.ship.coordinates, coord) if idx==0 else distance(path[idx-1]['coord'], coord))}")
			print(f"  - Flight Mode: {mode}")
			print(f"  - Refuel: {refuel}, Amount: {refuel_amount}")
			
			# If there are waypoint details available
			if self.df_sys_wps is not None:
				wp_data = self.df_sys_wps[self.df_sys_wps["wp_symbol"] == coord.wp]
				if not wp_data.empty:
					wp_type = wp_data["wp_type"].values[0]
					traits = wp_data["traits"].values[0] if "traits" in wp_data.columns else "Unknown"
					print(f"  - Type: {wp_type}")
					print(f"  - Traits: {traits}")
			
			print("------------------------------------------------------------")
	
	def select_ship(self):
		"""
		Let the user select a ship for the simulation
		"""
		ships = self.get_available_ships()
		
		if not ships:
			print("No ships available for simulation.")
			return None
		
		print("\nSelect a ship for navigation simulation:")
		for idx, ship in enumerate(ships):
			fuel_status = f"Fuel: {ship.fuel}/{ship.fuelCapacity}"
			location = f"Location: {ship.waypoint}"
			print(f"{idx+1}. {ship.name} ({ship.frame}) - {fuel_status} - {location}")
		
		choice = input("Enter ship number (or 0 to cancel): ")
		if choice.isdigit():
			idx = int(choice) - 1
			if idx == -1:  # User chose 0
				return None
			if 0 <= idx < len(ships):
				ship = ships[idx]
				
				# Ask if user wants to modify ship parameters
				print(f"\nCurrent ship parameters for {ship.name}:")
				print(f"1. Fuel: {ship.fuel}/{ship.fuelCapacity}")
				print(f"2. Current location: {ship.waypoint}")
				print("Do you want to modify any parameters?")
				modify = input("Enter parameter number to modify (or 0 to keep current values): ").strip().split()
				
				modified_fuel = None
				modified_fuel_capacity = None
				modified_waypoint = None
				
				if "1" in modify:
					fuel_input = input(f"Enter new fuel amount (max {ship.fuelCapacity}): ")
					if fuel_input.isdigit():
						modified_fuel = min(int(fuel_input), ship.fuelCapacity)
						print(f"Fuel set to {modified_fuel}")
				
				if "2" in modify:
					system = ship.system
					waypoints_df = self.get_waypoints_for_system(system)
					
					print("\nAvailable waypoints in the system:")
					for i, (_, wp) in enumerate(waypoints_df.iterrows()):
						print(f"{i+1}. {wp['wp_symbol']} - Type: {wp['wp_type']}")
					
					wp_choice = input("Enter waypoint number: ")
					if wp_choice.isdigit():
						wp_idx = int(wp_choice) - 1
						if 0 <= wp_idx < len(waypoints_df):
							selected_wp = waypoints_df.iloc[wp_idx]
							modified_waypoint = selected_wp["GmCrd"]
							print(f"Location set to {modified_waypoint.wp}")
				
				# Create a simulated ship with possibly modified parameters
				return SimulatedShip(
					ship,
					modified_fuel=modified_fuel,
					modified_fuel_capacity=modified_fuel_capacity,
					modified_waypoint=modified_waypoint
				)
			
		print("Invalid selection.")
		return None
	
	def select_target(self):
		"""
		Let the user select a target waypoint for the simulation
		"""
		if not self.ship:
			print("Please select a ship first.")
			return None
		
		system = self.ship.coordinates.sys
		waypoints_df = self.get_waypoints_for_system(system)
		self.df_sys_wps = waypoints_df  # Store for later use
		
		print("\nSelect target waypoint:")
		for i, (_, wp) in enumerate(waypoints_df.iterrows()):
			print(f"{i+1}. {str(wp['GmCrd'])}\t - Type: {wp['wp_type']}\t\t - Traits: {wp['traits']}")
		
		choice = input("Enter waypoint number (or 0 to cancel): ")
		if choice.isdigit():
			idx = int(choice) - 1
			if idx == -1:  # User chose 0
				return None
			if 0 <= idx < len(waypoints_df):
				selected_wp = waypoints_df.iloc[idx]
				return selected_wp["GmCrd"]
		
		print("Invalid selection.")
		return None
	
	def select_flight_mode(self):
		"""
		Let the user select a flight mode for the simulation
		"""
		print("\nSelect flight mode:")
		print("1. CRUISE (default)")
		print("2. DRIFT")
		print("3. BURN")
		print("4. STEALTH")
		
		choice = input("Enter your choice (or press Enter for default): ")
		
		if choice == "2":
			return "DRIFT"
		elif choice == "3":
			return "BURN"
		elif choice == "4":
			return "STEALTH"
		else:
			return "CRUISE"
	
	def toggle_print_paths(self):
		"""
		Toggle whether to print detailed path information
		"""
		print("\nDo you want to print detailed path information?")
		choice = input("Enter 'n' for no (or press Enter for default yes): ")
		return choice.lower() != 'n'
	
	def run_simulation(self):
		"""
		Main method to run the navigation simulation
		"""
		print("\n===== Navigation Simulation =====\n")
		
		# Step 1: Select a ship
		self.ship = self.select_ship()
		if not self.ship:
			print("Simulation cancelled.")
			return
		
		# Step 2: Select a target
		self.target_coord = self.select_target()
		if not self.target_coord:
			print("Simulation cancelled.")
			return
		
		# Step 3: Select flight mode
		self.flight_mode = self.select_flight_mode()
		
		# Step 4: Toggle detailed path printing
		self.print_paths = self.toggle_print_paths()
		
		# Run the simulation
		print(f"\nRunning navigation simulation:")
		print(f"Ship: {self.ship}")
		print(f"Starting location: {str(self.ship.coordinates)}")
		print(f"Fuel: {self.ship.fuel}/{self.ship.fuelCapacity}")
		print(f"Target: {str(self.target_coord)}")
		print(f"Flight mode: {self.flight_mode}")
		
		# Create the Navigation object and calculate the path
		nav = Navigation(self.Objman, self.df_sys_wps, self.market_df)
		path, total_cost, refuel_cost = nav.optimize_route(
			self.ship.coordinates,
			self.target_coord,
			self.ship.fuel,
			self.ship.fuelCapacity,
			self.flight_mode
		)
		
		# Display results
		if not path:
			print("\nNo valid path found! The target may be unreachable with current fuel or constraints.")
			return
		
		print(f"\nFound path with {len(path)} waypoints.")
		print(f"Total cost: {total_cost}")
		print(f"Total refuel cost: {refuel_cost}")
		
		# Print detailed path if requested
		if self.print_paths:
			# Calculate final fuel level after the journey
			final_fuel = self.ship.fuel
			for idx, step in enumerate(path):
				if step["refuel"]:
					final_fuel += step["refuel_amount"]
				
				# Estimate fuel consumption based on distance to next waypoint
				if idx != 0:  # Not the last step
					fuel_cost = self._calculate_fuel_cost(path[idx-1]["coord"], step["coord"], step["mode"])
					final_fuel -= fuel_cost
				else:
					fuel_cost = self._calculate_fuel_cost(self.ship.coordinates, step["coord"], step["mode"])
					final_fuel -= fuel_cost
			
			self.print_path(path, total_cost, final_fuel, refuel_cost)
		
		# Ask if user wants to save the simulation results
		print("\nSimulation completed.")
	
	def _calculate_fuel_cost(self, start: GameCoord, end: GameCoord, mode: str) -> int:
		"""
		Calculate the fuel cost for a hop between two waypoints.
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