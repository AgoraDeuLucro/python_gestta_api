import json
from time import sleep
import requests


class auth:
    """
    Classe base para autenticação e requisições na API Gestta.

    A API não possui rate limit oficial (é baseada no front-end),
    mas respeita respostas 429 utilizando backoff exponencial com retry automático.

    O token de acesso é enviado no header como:
        Authorization: JWT <token>
    """

    _DEFAULT_HEADERS = {
        "Origin": "https://app.gestta.com.br",
        "Referer": "https://app.gestta.com.br/",
    }

    def __init__(self, access_token="", base_url="", print_error=True):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/") if base_url else "https://api.gestta.com.br"
        self.print_error = print_error

    def login(self, email, password):
        """
        Realiza login na API e armazena o token de acesso na instância.

        Args:
            email (str): E-mail do usuário
            password (str): Senha do usuário

        Returns:
            dict: Resposta da API (inclui o token) ou dict vazio se falhou
        """
        url = self.base_url + "/core/login"
        headers = {**self._DEFAULT_HEADERS, "Content-Type": "application/json"}
        data = json.dumps({"email": email, "password": password})

        try:
            response = requests.post(url, headers=headers, data=data)
            if response.status_code in (200, 201):
                headers = response.headers
                if "authorization" in headers:
                    return {"access_token": headers["authorization"].replace("JWT ", "")}
                else:
                    return {}
            else:
                if self.print_error:
                    try:
                        print(f"Erro no login: {response.json()}")
                    except Exception:
                        print(f"Erro no login: {response.text}")
                return {}
        except Exception as e:
            if self.print_error:
                print(f"Erro na requisição de login: {e}")
            return {}

    def request(self, method="GET", url="", headers=None, params=None, data=None):
        """
        Executa uma requisição HTTP com retry automático em caso de 429.

        Implementa backoff exponencial: 1s, 2s, 4s, 8s, 16s (máx. 5 tentativas).
        """
        req_headers = dict(self._DEFAULT_HEADERS)
        if headers:
            req_headers.update(headers)

        if self.access_token:
            token = self.access_token
            if not token.startswith("JWT ") and not token.startswith("Bearer "):
                token = f"JWT {token}"
            req_headers["Authorization"] = token

        req_params = params or {}
        max_retries = 5
        wait = 1.0

        for attempt in range(max_retries + 1):
            match method:
                case "GET":
                    response = requests.get(url=url, params=req_params, headers=req_headers)
                case "POST":
                    response = requests.post(url=url, params=req_params, headers=req_headers, data=data)
                case "PUT":
                    response = requests.put(url=url, params=req_params, headers=req_headers, data=data)
                case "DELETE":
                    response = requests.delete(url=url, params=req_params, headers=req_headers, data=data)
                case "HEAD":
                    response = requests.head(url=url, params=req_params, headers=req_headers)
                case "OPTIONS":
                    response = requests.options(url=url, params=req_params, headers=req_headers)
                case _:
                    raise ValueError(f"Método HTTP inválido: {method}")

            if response.status_code in (200, 201):
                return response

            if response.status_code == 429:
                if attempt == max_retries:
                    if self.print_error:
                        print(f"Limite de requisições atingido (429). Máximo de tentativas ({max_retries}) alcançado.")
                    return None
                sleep(wait)
                wait = min(wait * 2, 60)
                continue

            if self.print_error:
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                print(
                    f"Erro no retorno da API Gestta\n"
                    f"Status: {response.status_code}\n"
                    f"URL: {url}\n"
                    f"Método: {method}\n"
                    f"Resposta: {body}"
                )

            if response.status_code in (403, 404):
                return None
            break

        return None


class relatorios(auth):
    """Relatórios da API Gestta."""

    def relatorio_tarefas(self, filter="CURRENT_MONTH", start_date=None, end_date=None, type="CUSTOMER_TASK"):
        """
        Gera o relatório de tarefas.

        Args:
            filter (str): Filtro de período. Ex.: "CURRENT_MONTH", "CUSTOM"
            start_date (str | None): Data inicial ISO 8601 (ex.: "2026-02-01T00:00:00-03:00").
                                     Obrigatório quando filter="CUSTOM".
            end_date (str | None): Data final ISO 8601 (ex.: "2026-02-28T23:59:59-03:00").
                                   Obrigatório quando filter="CUSTOM".
            type (str): Tipo de relatório. Padrão: "CUSTOMER_TASK"

        Returns:
            dict: Dados do relatório ou dict vazio se falhou
        """
        if not self.access_token:
            print("Token inválido")
            return {}

        url = self.base_url + "/core/customer/task/report"
        dates = {}
        if start_date:
            dates["startDate"] = start_date
        if end_date:
            dates["endDate"] = end_date

        payload: dict = {"type": type, "filter": filter}
        if dates:
            payload["dates"] = dates

        response = self.request(
            "POST",
            url=url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        if response:
            return response.json()
        return {}


class tarefas(auth):
    """Operações de Tarefas na API Gestta."""

    def pesquisar(self, status=None, type=None, company_user=None,
                  start_date=None, end_date=None, no_owner=False,
                  os_free=False, os_workflow=False, page=1, limit=10, **kwargs):
        """
        Pesquisa tarefas com filtros.

        Args:
            status (list[str] | None): Status das tarefas. Ex.: ["OPEN", "IMPEDIMENT"]
            type (list[str] | None): Tipos de tarefa. Ex.: ["SERVICE_ORDER", "RECURRENT", "ACCOUNTING"]
            company_user (list[str] | None): IDs dos usuários responsáveis
            start_date (str | None): Data inicial ISO 8601 (ex.: "2026-03-01T03:00:00.000Z")
            end_date (str | None): Data final ISO 8601 (ex.: "2026-04-01T02:59:59.999Z")
            no_owner (bool): Incluir tarefas sem responsável
            os_free (bool): Filtro OS livre
            os_workflow (bool): Filtro OS workflow
            page (int): Número da página (padrão: 1)
            limit (int): Quantidade de registros por página (padrão: 10)
            **kwargs: Parâmetros extras enviados no body

        Returns:
            dict: Resultado da pesquisa ou dict vazio se falhou
        """
        if not self.access_token:
            print("Token inválido")
            return {}

        url = self.base_url + "/core/customer/task/search"
        payload = {
            "no_owner": no_owner,
            "os_free": os_free,
            "os_workflow": os_workflow,
            "page": page,
            "limit": limit,
        }

        if status is not None:
            payload["status"] = status
        if type is not None:
            payload["type"] = type
        if company_user is not None:
            payload["company_user"] = company_user
        if start_date is not None:
            payload["start_date"] = start_date
        if end_date is not None:
            payload["end_date"] = end_date

        payload.update(kwargs)

        response = self.request(
            "POST",
            url=url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        if response:
            return response.json()
        return {}

    def ver(self, id_tarefa):
        """
        Retorna os detalhes de uma tarefa.

        Args:
            id_tarefa (str): ID da tarefa no Gestta

        Returns:
            dict: Dados da tarefa ou dict vazio se falhou
        """
        if not self.access_token:
            print("Token inválido")
            return {}

        url = self.base_url + f"/core/customer/task/{id_tarefa}"
        response = self.request("GET", url=url)

        if response:
            return response.json()
        return {}

    def baixar_documento(self, customer_task, document, customer, file):
        """
        Baixa um documento associado a uma tarefa.

        Args:
            customer_task (str): ID da tarefa do cliente
            document (str): ID do documento
            customer (str): ID do cliente
            file (str): ID do arquivo

        Returns:
            dict: Resposta da API ou dict vazio se falhou
        """
        if not self.access_token:
            print("Token inválido")
            return {}

        url = self.base_url + "/accounting/pendency/document/download"
        payload = {
            "customer_task": customer_task,
            "document": document,
            "customer": customer,
            "file": file,
        }

        response = self.request(
            "POST",
            url=url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        if response:
            return response.json()
        return {}


class clientes(auth):
    """Operações de Clientes na API Gestta."""

    def ver(self, id_cliente):
        """
        Retorna os dados de um cliente.

        Args:
            id_cliente (str): ID do cliente no Gestta

        Returns:
            dict: Dados do cliente ou dict vazio se falhou
        """
        if not self.access_token:
            print("Token inválido")
            return {}

        url = self.base_url + f"/core/customer/task/{id_cliente}"
        response = self.request("GET", url=url)

        if response:
            return response.json()
        return {}
    
    def pesquisar(self, active=True, page=1, limit=15, search=""):
        """
        Pesquisa clientes com filtros.

        Args:
            active (bool): Incluir apenas clientes ativos (padrão: True)
            page (int): Número da página (padrão: 1)
            limit (int): Quantidade de registros por página (padrão: 15)
            search (str): Termo de busca no nome do cliente

        Returns:
            dict: Resultado da pesquisa ou dict vazio se falhou
        """
        if not self.access_token:
            print("Token inválido")
            return {}

        url = self.base_url + "/admin/customer"
        payload = {
            "active": active,
            "page": page,
            "limit": limit,
            "search": search,
        }

        response = self.request("GET", url=url, params=payload)

        if response:
            return response.json()
        return {}
