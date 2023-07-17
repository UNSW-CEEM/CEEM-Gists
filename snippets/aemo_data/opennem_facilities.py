# Basic python script to download and restructure DUID and station data
# from the openNEM facilities dataset
#
# Copyright (C) 2023 Dylan McConnell
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
from typing import List, Optional

import pandas as pd
import requests
import simplejson
from pydantic import BaseModel

GEOJSON = "https://data.opennem.org.au/v3/geo/au_facilities.json"
LOCALDIR = "/path/to/local/dir/"
STATION_URL = "https://api.opennem.org.au/station/au/NEM/{}"


def get_master():
    """
    Download master geojson file from openNEM, returning JSON
    """
    response = requests.get(GEOJSON)
    return simplejson.loads(response.content)


def get_station(station_code: str = "LIDDELL"):
    """
    Download and store station json from openNEM
    """
    response = requests.get(STATION_URL.format(station_code))
    json = simplejson.loads(response.content)

    filename = station_filename(json["code"])
    with open(os.path.join(LOCALDIR, filename), "w") as f:
        simplejson.dump(json, f, indent=2)


def station_filename(code: str):
    """
    Simple function to replace problematic characters in station codes
    and return a filename
    """
    clean_code = code.replace("/", "_")
    return f"{clean_code}.json"


def load_station(station_code: str):
    """
    Load station json from local directory
    """
    filename = station_filename(station_code)
    with open(os.path.join(LOCALDIR, filename), "r") as f:
        return simplejson.load(f)


def station_generator(master_json):
    """
    Generator that yields the station code for every station in the NEM
    """
    for station in master_json["features"]:
        if station["properties"]["network"] == "NEM":
            yield station["properties"]["station_code"]


def download_all_stations():
    """
    Downloads all the station json data from the master list.
    """
    master_json = get_master()
    for station_code in station_generator(master_json):
        if station_code != "SLDCBLK":
            try:
                load_station(station_code)
            except FileNotFoundError:
                print("downloading ", station_code)
                get_station(station_code)


"""
Some pydantic models for validating openNEM data
"""


class DispatchUnit(BaseModel):
    network_region: str
    code: str
    fueltech: str
    capacity_registered: Optional[float] = None


class Location(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None


class Station(BaseModel):
    name: str
    code: str
    location: Location
    facilities: List[DispatchUnit]


def parse_station_data():
    """
    Parses all station data from the master list.
    Assumes all station json already downloaded.
    """
    master_json = get_master()
    data = []

    for station_code in station_generator(master_json):
        if station_code not in ["MWPS", "SLDCBLK"]:
            station_json = load_station(station_code)
            valid_station = Station(**station_json)
            data.append(flatten_station(valid_station))

    return pd.concat(data).reset_index(drop=True)


def flatten_station(valid_station: Station):
    """
    Simple function to convert a validated station to pandas dataframe
    (probably could be done neater / cleaner with pd.normalize_json)
    """
    d = []
    station_dict = valid_station.dict()
    for du in valid_station.facilities:
        data = du.dict()
        data["lat"] = station_dict["location"]["lat"]
        data["lon"] = station_dict["location"]["lng"]
        data["station_name"] = station_dict["name"]
        data["station_code"] = station_dict["code"]
        d.append(data)

    return pd.DataFrame(d)
