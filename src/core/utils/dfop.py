# dfop
import time
import pandas as pd

from core.utils.coord import distance


def mine_shps(df, sys=None):

	if any(i not in df.columns for i in ("mounts", "has_task", "nav.status", "cooldown.expiration", "nav.systemSymbol")):
		raise Exception("df lacks column(s): mounts, has_task, nav.status, cooldown.expiration, nav.systemSymbol")

	if sys is not None:	
		# ships.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) from https://stackoverflow.com/a/53342780
		return df[df.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) & 
												df["nav.systemSymbol"] == sys &
												~df["has_task"] &
												df["nav.status"].isin(["DOCKED", "IN_ORBIT"]) & 
												df["cooldown.expiration"].lt(int(time.time()))].copy()

	else:
		return df[df.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) & 
												~df["has_task"] &
												df["nav.status"].isin(["DOCKED", "IN_ORBIT"]) & 
												df["cooldown.expiration"].lt(int(time.time()))].copy()


def probe_shps(df, sys=None):

	if any(i not in df.columns for i in ("mounts", "has_task", "nav.status", "cooldown.expiration", "frame.name", "nav.systemSymbol")):
		raise Exception("df lacks column(s): mounts, has_task, nav.status, cooldown.expiration, frame.name, nav.systemSymbol")

	if sys is not None:	
		# ships.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) from https://stackoverflow.com/a/53342780
		return df[ df["frame.name"].str.fullmatch("Probe", case=False) & 
					df["nav.systemSymbol"] == sys &
					~df["has_task"] &
					df["nav.status"].isin(["DOCKED", "IN_ORBIT"]) & 
					df["cooldown.expiration"].lt(int(time.time()))].copy()

	else:
		return df[ df["frame.name"].str.fullmatch("Probe", case=False) & 
					~df["has_task"] &
					df["nav.status"].isin(["DOCKED", "IN_ORBIT"]) & 
					df["cooldown.expiration"].lt(int(time.time()))].copy()


def any_non_probe_shps(df):

	if "frame.name" not in df.columns:
		print(df.columns)
		raise Exception("df lacks column frame.name")

	# ships.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) from https://stackoverflow.com/a/53342780
	return df[ ~df["frame.name"].str.fullmatch("Probe", case=False) ].copy()


def traits_lookup(df, li_traits:list):

	if "traits" not in df.columns:
		raise Exception("df lacks column traits")

	return df[df["traits"].str.contains('|'.join(li_traits), na=False)].copy()


def wp_type_traits_lookup(df, li_wptype:list, li_traits:list):

	if "traits" not in df.columns or "wp_type" not in df.columns:
		raise Exception("df lacks column traits or wp_type")
	elif not df.wp_type.isin(li_wptype).any() and len(df[df["traits"].str.contains('|'.join(li_traits), na=False)]) == 0:
		# return empty dataframe, since nothing found
		return pd.DataFrame(columns=["id", "wp_symbol", "wp_type", "coords", "traits", "orbitals", "modifiers", "isUnderConstruction", "chart_by", "chart_time", "updated"])

	return df[df["traits"].str.contains('|'.join(li_traits), na=False) |
				df["wp_type"].isin(li_wptype)].copy()


def nearest(df, coord):
	df["dist_coord"] = df.apply(lambda x: distance(x.GmCrd, coord), axis=1)
	nearest_wp_dict = df[df["dist_coord"] == df["dist_coord"].min()].to_dict(orient="records")[0]

	return nearest_wp_dict["GmCrd"]


def furthest(df, coord):
    """
    Returns the waypoint that is furthest from the given coordinate
    
    Args:
        df: DataFrame containing waypoints with GmCrd column
        coord: GameCoord object to measure distance from
        
    Returns:
        GameCoord: furthest waypoint
    """
    df["dist_coord"] = df.apply(lambda x: distance(x.GmCrd, coord), axis=1)
    furthest_wp_dict = df[df["dist_coord"] == df["dist_coord"].max()].to_dict(orient="records")[0]

    return furthest_wp_dict["GmCrd"]


def nearest_multiple(df, coords:list, new_col:str, amt:int=2, filter_same_coords:bool=True):
	# coords is list of multiple GameCoord
	# amt is dictating how many nearest should be looked for
	if len(coords) < amt:
		amt = len(coords)

	# the wp part of a GmCrd can be different with multiple same coords x::y
	# also only create nearest coords for coords in same system as ship (being in df)
	if filter_same_coords:
		df[new_col] = df.apply(lambda x: sorted(list((distance(x.GmCrd, coord), coord) for coord in coords if coord.sys == x.GmCrd.sys and
																											coord.coords != x.GmCrd.coords
												))[:amt], axis=1)
	else:
		df[new_col] = df.apply(lambda x: sorted(list((distance(x.GmCrd, coord), coord) for coord in coords if coord.sys == x.GmCrd.sys
												))[:amt], axis=1)

	return df
