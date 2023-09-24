import logging

from PokescraperTrigger.standings import mainWorker
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    id = req.params.get('id')
    if not id:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            id = req_body.get('id')

    url = req.params.get('url')
    if not url:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            url = req_body.get('url')

    if id and url:
        ret = mainWorker(id, url, False, False)
        return ret
    else:
        return func.HttpResponse(
             "Missing required params id and url",
             status_code=400
        )
