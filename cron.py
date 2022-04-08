import os
import time
import datetime
import Pyro5.api
import schedule

import pymongo
from pymongo import MongoClient

db_uri = os.getenv("DB_URI")
client = MongoClient(db_uri)
db = client.surveys

def closing_surveys():
    # retrieve surveys to be closed
    surveys = list(db.surveys.find({ 'closed': False, 'due_date': { '$lte': datetime.datetime.now() }}))

    if len(surveys) > 0:
        print('surveys found: {0}'.format(len(surveys)))

    # iterate through the results
    for survey in surveys:
        # change it on the database
        db.surveys.update_one({ '_id': survey['_id'] }, { '$set': { 'closed': True }})

        # retrieving client ids from the subscription collection
        client_ids = [i['client_id'] for i in db.votes.find({ 'survey_id': survey['_id'] })]

        # retrieving the only a logged client
        clients = db.clients.find({ '_id': client_ids, 'logged': True })

        for client in client:
            # when a client is found, we build the Pyro5 proxy
            proxy = Pyro5.api.Proxy('PYRONAME:{0}'.format(client['pyro_ref']))

            try:
                # we try to notify the survey creator
                proxy.notify_closed_survey(survey)

            except suppress(Pyro5.errors.NamingError, Pyro5.errors.CommunicationError) as e:
                # in case of this client is offline or unreachable, we set it as logged
                db.clients.update_one({ _id: client['_id'] }, { '$set': { 'logged': True }})

schedule.every(15).seconds.do(closing_surveys)

print('starting scheduler...')

while True:
    schedule.run_pending()
    time.sleep(1)
