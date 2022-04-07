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

    print('surveys found: {0}'.format(len(surveys)))

    # iterate through the results
    for survey in surveys:
        # change it on the database
        db.surveys.update_one({ '_id': survey['_id'] }, { '$set': { 'closed': True }})

        # retrieving the only a logged client
        client = db.clients.find_one({ '_id': survey['created_by'], 'logged': False })

        # skip this if no client found
        if not client:
            continue

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