import json
import logging
import os
from datetime import datetime
from functools import reduce
from json import loads
from urllib import request, parse

import pandas as pd
import psycopg2
import requests

from website.predict_fuel_consumption.utils import common
from website.predict_fuel_consumption.utils.simple_speed import get_simple_art_snippets

FORMAT = '%(asctime)-11s %(module)s.%(funcName)s %(levelname)s: %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

application_name = os.getenv("APPLICATION_NAME", None)
api_key = str(os.getenv("HERE_API_KEY", "dummy"))

query_hist_tbl = "future_trips.querry_history"
query_hist_cols = ["slat", "slon", "elat", "elon", "weight", "dept_timestamp", "fuel_consumption"]
features = ['avg_speed', 'altitude_end', 'altitude_change', 'distance_travelled', 'speed_end', 'speed_diff', 'weight']


def fuel_consumption_prediction(slat, slon, elat, elon, weight, dept_time):
    headers = {"content-type": "application/json"}

    logger.info(f"Running application {application_name}")

    trips_df = pd.DataFrame({'slat': [slat], 'slon': [slon], 'elat': [elat], 'elon': [elon], 'weight': [weight],
                             'dept_timestamp': [dept_time]})

    # TODO verify format in which the date is passed
    trips_df['dept_timestamp'] = pd.to_datetime(trips_df['dept_timestamp'], format='%Y-%m-%d %H:%M:%S')
    tz = psycopg2.tz.FixedOffsetTimezone(offset=0, name=None)
    trips_df['dept_timestamp'] = pd.DatetimeIndex(trips_df['dept_timestamp']).tz_localize(tz)

    base_url = "https://router.hereapi.com/v8/routes"
    params = parse.urlencode({
        'transportMode': 'truck',
        'origin': f"{slat}, {slon}",
        'destination': f"{elat}, {elon}",
        'departureTime': trips_df['dept_timestamp'].dt.strftime("%Y-%m-%dT%H:%M:%SZ")[0],
        'return': 'polyline,summary,incidents,elevation',
        'spans': 'truckAttributes,names,baseDuration,duration,length,dynamicSpeedInfo,segmentId,speedLimit,functionalClass',
        'apiKey': api_key
    })

    resp = request.urlopen(f"{base_url}?{params}")
    trips_df['art_snippets'] = resp.read().decode("utf-8")
    trips_df['art_snippets'] = trips_df['art_snippets'].apply(lambda row: loads(row)['routes'][0]['sections'][0])
    trips_df['route_length'] = trips_df['art_snippets'].apply(lambda route: route['summary']['length'] / 1000)
    trips_df = trips_df[trips_df['art_snippets'].apply(lambda route: len(route['spans'])) > 4]
    trips_df['art_snippets'] = trips_df['art_snippets'].apply(lambda route: get_simple_art_snippets(route))

    art_snippets = trips_df.explode('art_snippets').reset_index()
    art_snippets = art_snippets.drop('art_snippets', 1).assign(**art_snippets['art_snippets'].apply(pd.Series))
    art_snippets['avg_speed'] = 3600 * art_snippets['distance_travelled'] / art_snippets['duration']
    art_snippets['speed_diff'] = art_snippets['speed_end'] - art_snippets['speed_start']
    art_snippets['altitude_change'] = art_snippets['altitude_end'] - art_snippets['altitude_start']

    # TODO formatting art_snippets into event
    # trips['art_snippets'] = trips[['slat', 'slon', 'elat', 'elon', 'fms_timestamp']].apply(
    #     lambda row: call_here_routing(row, "6vIecQ0SYsVSxF7SHHYc0ioxOUUsxVDJrwnNvjqdRiw"), axis=1, meta=dict)

    art_snippets['fuel_cons_pred'] = art_snippets.apply(lambda row: requests.post(resp=requests.post('http://serving.models-dev.tracks:8501/v1/models/mfund:predict',
                                            data=json.dumps(create_dict(row)),
                                            headers=headers)), axis=1)

    # art_snippets['fuel_cons_pred'] = model.predict(art_snippets[features], batch_size=10000)
    trips_df['fuel_consumption'] = art_snippets['fuel_cons_pred'].sum()
    logger.info(f"Fuel consumption {trips_df['fuel_consumption'][0]}")

    time_points = [dict(slon=float(trips_df["slon"][0]),
                        slat=float(trips_df["slat"][0]),
                        elon=float(trips_df["elon"][0]),
                        elat=float(trips_df["elat"][0]),
                        weight=float(trips_df["weight"][0]),
                        dept_timestamp=trips_df["dept_timestamp"][0],
                        fuel_consumption=float(trips_df["fuel_consumption"][0]))]

    columns = reduce(lambda col, columns: ', '.join([columns, col]), query_hist_cols)
    values = reduce(lambda col, columns: ')s, %('.join([columns, col]), query_hist_cols)
    values = '%(' + values + ')s'

    insert_statement = """insert into  %s(%s) values(%s) ON CONFLICT DO NOTHING""" % (query_hist_tbl, columns, values)

    common.execute_query(insert_statement, time_points)

    return {
        "fuel_consumption": trips_df["fuel_consumption"][0]
    }

def create_dict(row):
    recs = row.to_dict()
    inputs = dict((k, recs[k]) for k in features if k in recs)
    inputs["end_speed"] = inputs.pop("speed_end")
    inputs["weight_total"] = inputs.pop("weight")
    return {"inputs": inputs}


if __name__=='__main__':
    event = {'inputs': {
        'slat': 53.369991,
        'slon': 9.763927,
        'elat': 51.664072,
        'elon': 6.922277,
        'weight': 54000,
        'dept_time': datetime(2021, 2, 1, 16, 39, 58)}}

    slat = event['inputs']["slat"]
    slon = event['inputs']["slon"]
    elat = event['inputs']["elat"]
    elon = event['inputs']["elon"]
    weight = event['inputs']["weight"]
    dept_time = event['inputs']["dept_time"]
    fuel_consumption_prediction(slat, slon, elat, elon, weight, dept_time)
