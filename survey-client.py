import os
import cmd
import sys
import threading
import datetime
import json
import Pyro5.api

from contextlib import suppress
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

user_data = None

with open('/app/user.json', 'r') as f:
    data = json.load(f)

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
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Perguntando o nome do usuário
        self.username = None

        while not self.username:
            self.username = input('Por favor, digite seu nome: ')

        # Registramos o cliente no serviço de nomes, adicionamos uma metadata para agrupar todos os clientes.
        nameserver.register(pyro_ref, uri, metadata = {'survey.client'})

        # Buscando serviço de enquete no serviço de nomes.
        self.survey_server = Pyro5.api.Proxy('PYRONAME:survey.server')

        # Gerando a string da chave pública para registrar o cliente no serviço de enquete.
        public_bytes = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Registrando o usuário no serviço de enquetes e guardamos o retorno para uso futuro.
        status, data = self.survey_server.register(self.username, public_bytes.decode('ascii'), pyro_ref)

        if status == True:
            self.client_data = data
        else:
            raise Exception('Não conseguimos nos registrar no serviço de enquetes: {0}'.format(data))

        print("Olá, {0}! Bem-vindo ao serviço de enquetes! Digite 'help' para descobrir o que posso fazer!".format(self.username))

        self.daemon_thread = threading.Thread(target=daemon.requestLoop)

    def postcmd(self, stop, line):
        # todo: implementar notificações aqui

        return line

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
