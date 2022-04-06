import os
import uuid
import datetime
import base64
import serpent
import Pyro5.api

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import utils
from cryptography.hazmat.primitives.asymmetric import padding

from typing import Any

import pymongo
from pymongo import MongoClient

hostname = os.getenv("HOSTNAME")
db_uri = os.getenv("DB_URI")
client = MongoClient(db_uri)
db = client.surveys

print("Starting survey server {0}...".format(hostname))

class SurveyRegister(object):
    connection = None
    cursor = None

    def __init__(self, stufflist=[]):
        self.client_collection = db.clients
        self.survey_collection = db.surveys

    def persist_client(self, name: str, public_key: str, pyro_ref: str):
        data = {
            "_id": str(uuid.uuid4()),
            "name": name,
            "public_key": public_key,
            "pyro_ref": pyro_ref,
            "logged": True,
        }

        self.client_collection.insert_one(data)

        return data

    def persist_survey(self, title: str, created_by: str, local: str, due_date: datetime, options: list[str]):
        data = {
            "_id": str(uuid.uuid4()),
            "title": title,
            "created_by": created_by,
            "local": local,
            "due_date": datetime.datetime.fromisoformat('2022-04-08T12:00:00'),
            "options": options,
        }

        print("data")
        print(data)

        self.survey_collection.insert_one(data)

        return data

    def notify_clients(self, survey_data: dict):
        for client in self.client_collection.find({ 'logged': True }):
            client_proxy = Pyro5.api.Proxy('PYRONAME:{0}'.format(client['pyro_ref']))

            try:
                client_proxy.notify(survey_data)
            except (Pyro5.errors.NamingError, Pyro5.errors.CommunicationError) as e:
                self.set_logged(client['_id'], False)
                # self.client_collection.delete_one({ '_id': client['_id'] })

        return True

    def set_logged(self, _id: str, flag: bool):
        self.client_collection.update_one({ '_id': _id }, { '$set': { 'logged': flag }})

    @Pyro5.server.expose
    def register(self, name: str, public_key: str, pyro_ref: str) -> tuple[bool, dict]:
        if not name:
            return False, "invalid name"

        if not public_key:
            return False, "invalid public_key"

        if not pyro_ref:
            return False, "invalid pyro_ref"

        client_data = self.persist_client(name, public_key, pyro_ref)

        print("[{0}] {1}".format(client_data['_id'], client_data['name']))

        return True, client_data

    @Pyro5.server.expose
    def logout(self, _id: str) -> bool:
        self.set_logged(_id, False)

        print('[logout][success][{0}]'.format(_id))

        return True

    @Pyro5.server.expose
    def login(self, _id: str, signature) -> bool:
        # print('_id: {0}'.format(_id))

        # finding the client on the database
        client = self.client_collection.find_one({ "_id": _id })

        # if the client was not found
        if not client:
            return False, 'client not found'

        # loading its public key from database
        public_key = load_pem_public_key(client["public_key"].encode('utf-8'))

        # serpent helper
        signature = serpent.tobytes(signature)

        try:
            verification = public_key.verify(
                signature,
                _id.encode('utf-8'),
                hashes.SHA256()
            )

            self.set_logged(_id, True)

            print('[login][success][{0}]'.format(_id))
            return True, ''

        # on invalid signature, we log it and return false
        except InvalidSignature:
            print('[login][failure][{0}]'.format(_id))
            return False, 'invalid signature'

    @Pyro5.server.expose
    def get_available_surveys(self) -> list:
        surveys = []

        for row in self.survey_collection.find({ "due_date": { "$gte": datetime.datetime.now() }}):
            row['created_by'] = self.client_collection.find_one({ '_id': row['created_by'] })['name']
            surveys.append(row)

        return surveys

    @Pyro5.server.expose
    def create_survey(self, title: str, created_by: str, local: str, due_date: datetime, options: list[datetime]) -> tuple[bool, Any]:
        if not title:
            return False, "invalid title"

        if not created_by:
            return False, "invalid created_by"

        if not local:
            return False, "invalid local"

        if not title:
            return False, "invalid title"

        if not due_date:
            return False, "invalid due_date"

        if len(options) == 0:
            return False, "invalid options"

        survey = self.persist_survey(title, created_by, local, due_date, options)

        print('[create_survey][success][{0}]'.format(survey['_id']))

        return True, survey

daemon = Pyro5.server.Daemon(host = hostname) # make a Pyro daemon
ns = Pyro5.api.locate_ns()                    # find the name server
uri = daemon.register(SurveyRegister)         # register the survey register as a Pyro object

if __name__ == '__main__':
    # register the object with a name in the name server
    ns.register("survey.server", uri)

    print("Ready.")
    daemon.requestLoop() # start the event loop of the server to wait for calls
