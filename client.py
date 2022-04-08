import os
import cmd
import sys
import threading
import datetime
import json
import queue
import Pyro5.api

from contextlib import suppress

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.primitives.asymmetric import utils
from cryptography.hazmat.primitives.asymmetric import padding

hostname = os.getenv('HOSTNAME')
pyro_ref = 'survey.client.{0}'.format(hostname)

pyro5_lives = True

def should_pyro5_continues():
    return pyro5_lives

PRIVATE_KEY_PATH = "/app/private.pem"
USER_DATA_PATH = "/app/user.json"

closed_survey_queue = queue.Queue()
new_survey_queue = queue.Queue()
vote_queue = queue.Queue()

# retrieving private
if os.path.exists(PRIVATE_KEY_PATH):
    # loading private key from disk
    with open(PRIVATE_KEY_PATH, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password = None,
        )

else:
    # generating the private file
    private_key = dsa.generate_private_key(
        key_size = 1024,
    )

    # writing it to disk
    with open(PRIVATE_KEY_PATH, "w") as key_file:
        pem = private_key.private_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PrivateFormat.PKCS8,
            encryption_algorithm = serialization.NoEncryption()
        )

        for i in pem.splitlines():
            key_file.write('{0}\n'.format(i.decode('ASCII')))

# loading user data
user_data = None

if os.path.exists(USER_DATA_PATH):
    with open(USER_DATA_PATH, 'r') as f:
        user_data = json.load(f)

messages = []

def start_pyro5_server():
    print('Starting Pyro daemon...')
    # Pyro
    daemon = Pyro5.server.Daemon(host = hostname)
    uri = daemon.register(SurveyClient)

    # Registramos o cliente no serviço de nomes, adicionamos uma metadata para agrupar todos os clientes.
    nameserver = Pyro5.api.locate_ns()
    nameserver.register(pyro_ref, uri, metadata = {'survey.client'})

    daemon.requestLoop(should_pyro5_continues)

class SurveyClient:
    def start():
        pass

    def stop():
        pass

    @Pyro5.server.expose
    def notify_new_survey(self, survey):
        new_survey_queue.put(survey)

        return True

    @Pyro5.server.expose
    def notify_closed_survey(self, survey):
        closed_survey_queue.put(survey)

        return True

    @Pyro5.server.expose
    def notify_vote(self, survey, client_name, option):
        vote_queue.put({
            'survey': survey,
            'client_name': client_name,
            'option': option,
        })

        return True

class SurveyPrompt(cmd.Cmd):
    prompt = '>>> '

    def __init__(self, stufflist=[]):
        cmd.Cmd.__init__(self)

        # Perguntando o nome do usuário
        self.username = None

        if user_data and user_data['name']:
            self.username = user_data['name']

        while not self.username:
            self.username = input('Por favor, digite seu nome: ')

        # Buscando serviço de enquete no serviço de nomes.
        self.survey_server = Pyro5.api.Proxy('PYRONAME:survey.server')

        status = False
        data = 'unknown'

        # already have user data?
        if user_data and user_data['_id']:
            _id = user_data['_id']

            # signature = private_key.sign(_id.encode('utf-8'), hashes.SHA256())
            signature = self.sign_message(_id)

            status, _ = self.survey_server.login(_id, signature)

            data = user_data

        else:
            # Gerando a string da chave pública para registrar o cliente no serviço de enquete.
            public_bytes = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # Registrando o usuário no serviço de enquetes e guardamos o retorno para uso futuro.
            status, data = self.survey_server.register(self.username, public_bytes.decode('ascii'), pyro_ref)

            with open(USER_DATA_PATH, 'w') as f:
                json.dump(data, f, sort_keys=True)

        if status == True:
            self.client_data = data

        else:
            raise Exception('Não conseguimos nos registrar no serviço de enquetes: {0}'.format(data))

        print("Olá, {0}! Bem-vindo ao serviço de enquetes! Digite 'help' para descobrir o que posso fazer!".format(self.username))

        self.pyro_thread = threading.Thread(target=start_pyro5_server, args=(), daemon=True)
        self.pyro_thread.start()

    # signing a message
    def sign_message(self, message: str):
        return private_key.sign(message.encode('utf-8'), hashes.SHA256())

    # used to avoid accidentally running the last command again
    def emptyline(self):
        pass

    def postcmd(self, stop, line):
        if (new_survey_queue.empty() and closed_survey_queue.empty() and vote_queue.empty()):
            print('Nenhuma notificação.')

        while not new_survey_queue.empty():
            survey = new_survey_queue.get()
            print('Notificação: uma nova enquete foi criada: "{0}"'.format(survey['title']))
            new_survey_queue.task_done()

        while not closed_survey_queue.empty():
            survey = closed_survey_queue.get()
            print('Notificação: a enquete "{0}" foi finalizada.'.format(survey['title']))
            closed_survey_queue.task_done()

        while not vote_queue.empty():
            vote = vote_queue.get()
            print('Notificação: a opção "{0}" da enquete "{1}" recebeu um voto de "{2}".'.format(vote['option'], vote['client_name'], vote['survey']['title']))
            vote_queue.task_done()

        return stop

    def do_nova(self, arg):
        'Cria uma nova enquete. Os outros usuários do serviço são notificados.'

        title = None
        local = None
        due_date = None

        while not title:
            title = input('Qual o título da enquete? ')

        while not local:
            local = input('Qual o local do evento? ')

        while not due_date:
            aux = input('Qual a data limite para votação da enquete? (Formato: dd/mm/aaaa hh:ii): ')
            with suppress(ValueError): due_date = datetime.datetime.strptime(aux, '%d/%m/%Y %H:%M')

        print('Adicione três opções para sua enquete, no formato: \'dd/mm/aaaa hh:ii\'.')

        count = 1
        options = []

        while len(options) < 3:
            # while the options is not properly filled, we loop
            option = None

            while not option:
                aux = input('Opção #{0}: '.format(count))
                with suppress(ValueError): option = datetime.datetime.strptime(aux, '%d/%m/%Y %H:%M')

            options.append(aux)
            count += 1

        created_by = self.client_data['_id']

        status, survey = self.survey_server.create_survey(title, created_by, local, due_date, options)

        if status == False:
            print('Não conseguimos criar a enquete.')

    def do_listar(self, arg):
        'Lista as enquetes disponíveis.'

        client_id = self.client_data['_id']

        status, surveys = self.survey_server.list_available_surveys(client_id, self.sign_message(client_id))

        if len(surveys) > 0:
            print('Enquetes disponíveis:')
            print('-----------')

            for survey in surveys:
                print('ID: {0}'.format(survey['_id']))
                print('Título: {0}'.format(survey['title']))
                print('Criado por: {0}'.format(survey['created_by']))
                if survey['closed']:
                    print('Status: encerrada')
                else:
                    print('Status: disponível')
                print('Opções:')
                for survey_option in survey['options']:
                    print(survey_option)
                print('-----------')

        else:
            print('Nenhuma enquete encontrada')
            print('-----------')

    def do_votar(self, arg):
        'Vota em uma opção de uma determinada enquete...'

        survey_id = None
        survey = None

        while not survey_id:
            survey_id = input('Qual o ID da enquete? ')

        option = None

        while not option:
            option = input('Em qual opção você deseja votar? ')

        status, message = self.survey_server.vote_survey_option(self.client_data['_id'], survey_id, option, self.sign_message(option))

        if status:
            print('Voto registrado!')

        else:
            print('Erro: {0}'.format(message))

    def do_consultar(self, survey_id=None):
        'Consulta uma enquete no serviço'

        while not survey_id:
            survey_id = input('Qual o ID da enquete? ')

        client_id = self.client_data['_id']

        status, data = self.survey_server.consult_survey(client_id, survey_id, self.sign_message(client_id))

        if status:
            print('Dados da enquete:')
            print('ID: {0}'.format(data['_id']))
            print('Título: {0}'.format(data['title']))
            print('Criado por: {0}'.format(data['created_by']))
            print('Opções:')
            for survey_option in data['options']:
                print(survey_option)
            print('Votos:')
            for option in data['votes']:
                print('{0}: {1}'.format(option, ', '.join(data['votes'][option])))

        else:
            print('Erro: {0}'.format(data))


    def do_sair(self, arg):
        'Desregistra você do serviço de enquete e encerra esse cliente.'

        print('Desregistrando do serviço de enquete...')
        self.survey_server.logout(self.client_data['_id'])
        print('Até a próxima!')

        # this will trigger the exit of Pyro5 daemon
        pyro5_lives = False

        sys.exit(0)

# Pseudo-terminal
sp = SurveyPrompt(sys.argv[1:])

if __name__ == '__main__':
    sp.cmdloop()
