# Enquetes

São aplicações client-server escritas em Python utilizando o middleware Pyro5
para fornecer as camadas de abstração necessárias para comunicação entre elas.

Ambas foram escritas para serem executadas em containers Docker.

## Server

Oferece através de um **name server** do Pyro alguns métodos para invocação
remota.

Os mesmos clientes que utilizam os métodos também precisam se registrar no
**name server** e informar o endereço obtido ao server para receberem
notificações sobre a criação de enquetes.

Expõe os seguintes métodos:
* `register(name: str, public_key: str, pyro_ref: str) -> tuple[bool, dict])`
* `login(_id: str, signature) -> bool`
* `logout(_id: str) -> bool`
* `list_available_surveys() -> list`
* `create_survey(title: str, created_by: str, local: str, due_date: datetime, options: list[datetime]) -> tuple[bool, Any]`
* `vote_survey_option(_id: str, signature, survey_id: str, option: str) -> bool`

## Client

Expõe os seguintes métodos:
* `notify_vote`
