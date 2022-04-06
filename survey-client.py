import os
import cmd
import sys
import threading
import datetime
import json
import serpent
import Pyro5.api

from contextlib import suppress

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.primitives.asymmetric import utils
from cryptography.hazmat.primitives.asymmetric import padding

SERPENT_BYTES_REPR = True

PRIVATE_KEY_PATH = "/app/private.pem"
USER_DATA_PATH = "/app/user.json"

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

class SurveyClient(object):
    @Pyro5.server.expose
    def subscribe(self, data):
        print('Nova enquete criada: {0}'.format(data['title']))
        return True

class SurveyPrompt(cmd.Cmd):
    prompt = '>>> '

    def __init__(self, stufflist=[]):
        cmd.Cmd.__init__(self)

        # Gerando uma chave privada
        self.private_key = private_key

        # Perguntando o nome do usuário
        self.username = None

        if user_data and user_data['name']:
            self.username = user_data['name']

        while not self.username:
            self.username = input('Por favor, digite seu nome: ')

        # Registramos o cliente no serviço de nomes, adicionamos uma metadata para agrupar todos os clientes.
        nameserver.register(pyro_ref, uri, metadata = {'survey.client'})

        # Buscando serviço de enquete no serviço de nomes.
        self.survey_server = Pyro5.api.Proxy('PYRONAME:survey.server')

        status = False
        data = 'unknown'

        # already have user data?
        if user_data and user_data['_id']:
            _id = user_data['_id']

            signature = private_key.sign(_id.encode('utf-8'), hashes.SHA256())

            status, _ = self.survey_server.login(_id, signature)

            data = user_data

        else:
            # Gerando a string da chave pública para registrar o cliente no serviço de enquete.
            public_bytes = self.private_key.public_key().public_bytes(
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

        # self.daemon_thread = threading.Thread(target=daemon.requestLoop)

    def _login(_id, private_key):
        signature = private_key.sign(_id.encode('utf-8'), hashes.SHA256())

        status, _ = self.survey_server.login(_id, signature)

        data = user_data

    def postcmd(self, stop, line):
        # todo: implementar notificações aqui

        return stop

    def do_nova(self, arg):
        'Cria uma nova enquete. Os outros usuários do serviço são notificados.'

        title      = None
        local      = None
        due_date   = None

        while not title:
            title = input('Qual o título da enquete? ')

        while not local:
            local = input('Qual o local do evento? ')

        while not due_date:
            aux = input('Qual a data limite para votação da enquete? (Formato: dd/mm/aaaa hh:ii): ')
            with suppress(ValueError): due_date = datetime.datetime.strptime(aux, '%d/%m/%Y %H:%M')

        print('Adicione três opções para sua enquete, no formato: \'dd/mm/aaaa hh:ii\'.')
        # print('Pressione ctrl+d quando terminar de adicionar.')

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

        if status == True:
            print(survey)
        else:
            print('Não conseguimos criar a enquete: {0}'.format(data))

    def do_listar(self, arg):
        'Lista as enquetes disponíveis.'

        surveys = self.survey_server.get_available_surveys()

        if len(surveys) > 0:
            print('Enquetes disponíveis:')

            for survey in surveys:
                print('-----------')
                print('Título: {0}'.format(survey['title']))
                print('Criado por: {0}'.format(survey['created_by']))
                print('-----------')

        else:
            print('Nenhuma enquete encontrada')

    def do_votar(self, arg):
        'Vota em uma opção de uma determinada enquete...'
        raise Exception('Não implementado')

    def do_sair(self, arg):
        'Deregistra você do serviço de enquete e encerra esse cliente.'

        print('Deregistrado do serviço de enquete! Até a próxima!')
        self.survey_server.unregister(self.client_data['_id'])
        sys.exit(0)

hostname = os.getenv('HOSTNAME')

# Pyro
daemon      = Pyro5.server.Daemon(host = hostname) # make a Pyro daemon
nameserver  = Pyro5.api.locate_ns()            # find the name server
uri         = daemon.register(SurveyClient) # register the survey client as a Pyro object
pyro_ref = 'survey.client.{0}'.format(hostname)

# Pseudo-terminal
sp = SurveyPrompt(sys.argv[1:])

if __name__ == '__main__':
    sp.cmdloop()
