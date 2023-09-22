import json
from standings import mainWorker

def lambda_handler(event, context):
    if "id" not in event:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing required id param')
        }
    if "url" not in event:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing required url param')
        }

    ret = mainWorker(event['id'], event['url'], False, False)
    return ret
