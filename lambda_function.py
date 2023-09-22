import json
from standings import mainWorker

def lambda_handler(event, context):
    if event['directory'] == None:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing required directory param')
        }
    if event['link'] == None:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing required link param')
        }

    mainWorker(event['directory'], event['link'], event['getDecklists'], event['getRoster'])
    return {
        'statusCode': 200,
        'body': json.dumps('Worker worked!')
    }
