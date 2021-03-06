import httplib2
import json
import logging
import sys

try:
    import apiclient.errors
    from apiclient.discovery import build
    from apiclient.errors import HttpError
    from oauth2client.client import SignedJwtAssertionCredentials
except ImportError:
    print "Missing dependencies. Please install google-api-python-client and oauth2client."
    print "You can use pip:   pip install google-api-python-client oauth2client"

from redash.utils import JSONEncoder

def bigquery(connection_string):
    def load_key(filename):
        f = file(filename, "rb")
        try:
            return f.read()
        finally:
            f.close()

    def get_bigquery_service():
        scope = [
            "https://www.googleapis.com/auth/bigquery",
        ]

        credentials = SignedJwtAssertionCredentials(connection_string["serviceAccount"], load_key(connection_string["privateKey"]), scope=scope)
        http = httplib2.Http()
        http = credentials.authorize(http)

        return build("bigquery", "v2", http=http)

    def query_runner(query):
        bigquery_service = get_bigquery_service()

        jobs = bigquery_service.jobs()
        job_data = {
            "configuration": {
                "query": {
                    "query": query,
                }
            }
        }

        logging.debug("bigquery got query: %s", query)

        project_id = connection_string["projectId"]

        try:
            insert_response = jobs.insert(projectId=project_id, body=job_data).execute()
            current_row = 0
            query_reply = jobs.getQueryResults(projectId=project_id, jobId=insert_response['jobReference']['jobId'], startIndex=current_row).execute()

            rows = []
            field_names = []
            for f in query_reply["schema"]["fields"]:
                field_names.append(f["name"])

            while(("rows" in query_reply) and current_row < query_reply['totalRows']):
                for row in query_reply["rows"]:
                    row_data = {}
                    column_index = 0
                    for cell in row["f"]:
                        row_data[field_names[column_index]] = cell["v"]
                        column_index += 1

                    rows.append(row_data)

                current_row += len(query_reply['rows'])
                query_reply = jobs.getQueryResults(projectId=project_id, jobId=query_reply['jobReference']['jobId'], startIndex=current_row).execute()

            columns = [{'name': name,
                        'friendly_name': name,
                        'type': None} for name in field_names]

            data = {
                "columns" : columns,
                "rows" : rows
            }
            error = None

            json_data = json.dumps(data, cls=JSONEncoder)
        except apiclient.errors.HttpError, e:
            json_data = None
            error = e.args[1]
        except KeyboardInterrupt:
            error = "Query cancelled by user."
            json_data = None
        except Exception as e:
            raise sys.exc_info()[1], None, sys.exc_info()[2]

        return json_data, error


    return query_runner
