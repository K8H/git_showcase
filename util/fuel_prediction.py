import json
from typing import List

import boto3
import requests

route53_client = boto3.client('route53')


def get_mfund_predictions(stage: str) -> List[str]:
    headers = {"content-type": "application/json"}

    zone_id = route53_client.list_hosted_zones_by_name(
        DNSName=f"serving.models-{stage}.tracks"
    )["HostedZones"][0]["Id"].split('/')[-1]

    record_sets = route53_client.list_resource_record_sets(
        HostedZoneId=zone_id
    )['ResourceRecordSets']

    resp = requests.post(resp = requests.post('http://serving.models-dev.tracks:8501/v1/models/mfund:predict',
                              data=json.dumps(event),
                              headers=headers)

    return [
        record['ResourceRecords'][0]['Value'] for record in record_sets
        if record['Type'] == 'A'
    ]


def lambda_handler(event, context):
    return get_mfund_predictions(event['stage'])


if __name__ == "__main__":
    event = {"stage": "dev",
             'queryStringParameters': {
                 "start_speed",
                 "end_speed",
                 "distance_travelled",
                 "weight_total",
                 "avg_tco_based_speed",
                 "min_tco_based_speed",
                 "max_tco_based_speed",
                 "avg_engine_speed",
                 "min_engine_speed",
                 "max_engine_speed"}}

    print(get_mfund_predictions(event["stage"], event)