import io
import unittest

from app import criar_app
from util_testes import SENHA, dados_partida, nova_plataforma


class BaseApi(unittest.TestCase):
    def setUp(self):
        self.plataforma, self.relogio = nova_plataforma()
        import tempfile
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.app = criar_app(self.plataforma, self.pasta.name, limite_auth=None)
        self.http = self.app.test_client()

    def chamar(self, metodo, url, corpo=None, token=None, **extras):
        cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
        if corpo is not None and "data" not in extras:
            extras["json"] = corpo
        return getattr(self.http, metodo)(f"/api{url}", headers=cabecalhos, **extras)

    def entrar(self, email):
        return self.chamar("post", "/auth/login", {"email": email, "senha": SENHA}).get_json()["accessToken"]

    def cadastrar(self, papel, n, **extras):
        base = {"nome": f"{papel} {n}", "email": f"{papel}{n}@t.com", "senha": SENHA, "cidade": "Uberlândia"}
        if papel == "jogador":
            base.update({"bairro": "Centro", "posicoes": [{"posicao": "ALA", "principal": True}, {"posicao": "FIXO"}]})
        if papel == "quadra":
            base.update({"nomeFantasia": "Arena", "endereco": "Rua A", "bairro": "Centro", "precoHora": 120})
        base.update(extras)
        resp = self.chamar("post", f"/auth/cadastro/{papel}", base)
        self.assertEqual(resp.status_code, 201, resp.get_json())
        login = self.chamar("post", "/auth/login", {"email": base["email"], "senha": SENHA})
        self.assertEqual(login.status_code, 200)
        return {"id": resp.get_json()["id"], **login.get_json()}


class TestContratoHttp(BaseApi):
    def test_healthcheck_e_rotas_protegidas(self):
        self.assertEqual(self.chamar("get", "/health").status_code, 200)
        resp = self.chamar("get", "/partidas")
        self.assertEqual(resp.status_code, 401)
        corpo = resp.get_json()
        self.assertEqual(corpo["codigo"], "NAO_AUTENTICADO")
        for chave in ("mensagem", "detalhes", "traceId"):
            self.assertIn(chave, corpo)

    def test_cadastro_201_location_e_nunca_expoe_senha(self):
        resp = self.chamar("post", "/auth/cadastro/organizador",
                           {"nome": "O", "email": "o@t.com", "senha": SENHA, "cidade": "X"})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.headers["Location"].startswith("/api/organizadores/"))
        usuario = self.cadastrar("jogador", 1)
        texto = self.chamar("get", "/usuarios/eu", token=usuario["accessToken"]).get_data(as_text=True)
        self.assertNotIn("senha", texto.lower())
        self.assertNotIn("hash", texto.lower())

    def test_validacao_e_conflitos_de_cadastro(self):
        self.cadastrar("jogador", 1)
        dup = self.chamar("post", "/auth/cadastro/jogador", {"nome": "X", "email": "JOGADOR1@t.com", "senha": SENHA,
                          "cidade": "A", "posicoes": [{"posicao": "ALA", "principal": True}]})
        self.assertEqual((dup.status_code, dup.get_json()["codigo"]), (409, "EMAIL_JA_CADASTRADO"))
        ruim = self.chamar("post", "/auth/cadastro/organizador", {"nome": "X", "email": "x@x.com", "senha": "curta", "cidade": "A"})
        self.assertEqual(ruim.status_code, 400)
        sem_json = self.chamar("post", "/auth/login", data="isto não é json", content_type="text/plain")
        self.assertEqual(sem_json.status_code, 400)

    def test_papel_errado_403_recurso_inexistente_404(self):
        jog = self.cadastrar("jogador", 1)
        self.assertEqual(self.chamar("post", "/partidas", {}, jog["accessToken"]).status_code, 403)
        self.assertEqual(self.chamar("get", "/jogadores", token=jog["accessToken"]).status_code, 403)
        self.assertEqual(self.chamar("get", "/partidas/inexistente", token=jog["accessToken"]).status_code, 404)
        self.assertEqual(self.chamar("get", "/rota-que-nao-existe", token=jog["accessToken"]).status_code, 404)

    def test_paginacao_com_limite_maximo_e_ordenacao_invalida(self):
        org = self.cadastrar("organizador", 1)
        resp = self.chamar("get", "/partidas?limit=500&page=1", token=org["accessToken"])
        self.assertEqual(resp.get_json()["meta"]["limit"], 50)
        self.assertEqual(self.chamar("get", "/partidas?sort=senha:asc", token=org["accessToken"]).status_code, 400)
        self.assertEqual(self.chamar("get", "/partidas?page=0", token=org["accessToken"]).status_code, 400)

    def test_refresh_rotativo_e_logout_via_http(self):
        jog = self.cadastrar("jogador", 1)
        novo = self.chamar("post", "/auth/refresh", {"refreshToken": jog["refreshToken"]})
        self.assertEqual(novo.status_code, 200)
        self.assertEqual(self.chamar("post", "/auth/refresh", {"refreshToken": jog["refreshToken"]}).status_code, 401)
        t = novo.get_json()
        self.assertEqual(self.chamar("post", "/auth/logout", {"refreshToken": t["refreshToken"]}, t["accessToken"]).status_code, 204)
        self.assertEqual(self.chamar("get", "/usuarios/eu", token=t["accessToken"]).status_code, 401)

    def test_limite_de_requisicoes_nas_rotas_de_auth(self):
        app = criar_app(self.plataforma, self.pasta.name, limite_auth=3)
        http = app.test_client()
        codigos = [http.post("/api/auth/login", json={"email": "a@a.com", "senha": "x"}).status_code for _ in range(5)]
        self.assertEqual(codigos, [401, 401, 401, 429, 429])


class TestFoto(BaseApi):
    PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100

    def enviar(self, token, conteudo, nome="foto.png"):
        return self.chamar("put", "/jogadores/eu/foto", token=token, data={"foto": (io.BytesIO(conteudo), nome)},
                           content_type="multipart/form-data")

    def test_foto_valida_e_servida(self):
        jog = self.cadastrar("jogador", 1)
        resp = self.enviar(jog["accessToken"], self.PNG)
        self.assertEqual(resp.status_code, 200)
        url = resp.get_json()["fotoUrl"]
        with self.http.get(url) as servida:
            self.assertEqual(servida.status_code, 200)

    def test_formato_invalido_mesmo_com_extensao_de_imagem(self):
        jog = self.cadastrar("jogador", 1)
        resp = self.enviar(jog["accessToken"], b"<script>alert(1)</script>", "x.png")
        self.assertEqual((resp.status_code, resp.get_json()["codigo"]), (400, "FORMATO_INVALIDO"))

    def test_foto_acima_de_2mb_recusada(self):
        jog = self.cadastrar("jogador", 1)
        resp = self.enviar(jog["accessToken"], self.PNG + b"0" * (2 * 1024 * 1024))
        self.assertEqual(resp.status_code, 413)

    def test_so_jogador_envia_foto(self):
        org = self.cadastrar("organizador", 1)
        self.assertEqual(self.enviar(org["accessToken"], self.PNG).status_code, 403)


class TestFluxoCompleto(BaseApi):
    def test_cadastro_ate_avaliacao(self):
        org = self.cadastrar("organizador", 1)
        jogs = [self.cadastrar("jogador", n) for n in (1, 2)]
        outra_cidade = self.cadastrar("jogador", 3, cidade="Araguari")
        o, j1, j2 = org["accessToken"], jogs[0]["accessToken"], jogs[1]["accessToken"]

        # partida criada → matchmaking gera propostas só para quem é da cidade
        resp = self.chamar("post", "/partidas", dados_partida(self.relogio, totalVagas=2), o)
        self.assertEqual(resp.status_code, 201)
        partida = resp.get_json()
        self.assertTrue(resp.headers["Location"].endswith(partida["id"]))
        self.assertEqual(partida["vagasRestantes"], 2)
        propostas = self.chamar("get", "/propostas", token=j1).get_json()["dados"]
        self.assertEqual([p["partida"]["id"] for p in propostas], [partida["id"]])
        self.assertEqual(self.chamar("get", "/propostas", token=outra_cidade["accessToken"]).get_json()["dados"], [])

        # jogador 1 aceita a proposta (vira candidatura); jogador 2 se candidata direto
        self.assertEqual(self.chamar("post", f"/propostas/{propostas[0]['id']}/visualizacao", token=j1).status_code, 204)
        aceite = self.chamar("post", f"/propostas/{propostas[0]['id']}/aceite", {}, j1)
        self.assertEqual((aceite.status_code, aceite.get_json()["status"]), (201, "PENDENTE"))
        direta = self.chamar("post", f"/partidas/{partida['id']}/candidaturas", {"posicao": "FIXO"}, j2)
        self.assertEqual(direta.status_code, 201)
        dup = self.chamar("post", f"/partidas/{partida['id']}/candidaturas", {}, j2)
        self.assertEqual((dup.status_code, dup.get_json()["codigo"]), (409, "CANDIDATURA_DUPLICADA"))

        # só o criador vê e decide as candidaturas
        self.assertEqual(self.chamar("get", f"/partidas/{partida['id']}/candidaturas", token=j1).status_code, 403)
        lista = self.chamar("get", f"/partidas/{partida['id']}/candidaturas?status=PENDENTE", token=o).get_json()["dados"]
        self.assertEqual(len(lista), 2)
        for c in lista:
            self.assertEqual(self.chamar("post", f"/candidaturas/{c['id']}/aprovacao", token=o).status_code, 200)
        detalhe = self.chamar("get", f"/partidas/{partida['id']}", token=j1).get_json()
        self.assertEqual((detalhe["status"], detalhe["vagasRestantes"]), ("COMPLETA", 0))
        participantes = self.chamar("get", f"/partidas/{partida['id']}/participantes", token=j1).get_json()["dados"]
        self.assertEqual(len(participantes), 2)
        self.assertNotIn("email", participantes[0])

        # avaliar antes de encerrar é conflito; iniciar antes do horário também
        corpo = {"avaliadoId": jogs[1]["id"], "nota": 5}
        self.assertEqual(self.chamar("post", f"/partidas/{partida['id']}/avaliacoes", corpo, j1).status_code, 409)
        self.assertEqual(self.chamar("post", f"/partidas/{partida['id']}/inicio", token=o).status_code, 409)
        self.relogio.agora = self.plataforma.obter_partida(partida["id"]).inicio
        o, j1 = self.entrar("organizador1@t.com"), self.entrar("jogador1@t.com")  # tokens de 15 min expiraram
        self.assertEqual(self.chamar("post", f"/partidas/{partida['id']}/inicio", token=o).status_code, 200)
        self.assertEqual(self.chamar("post", f"/partidas/{partida['id']}/encerramento", token=o).status_code, 200)

        # quem não participou não avalia (403); participantes e criador avaliam
        fora = self.entrar("jogador3@t.com")
        self.assertEqual(self.chamar("post", f"/partidas/{partida['id']}/avaliacoes", corpo, fora).status_code, 403)
        pend = self.chamar("get", f"/partidas/{partida['id']}/avaliacoes/pendentes", token=j1).get_json()["dados"]
        self.assertEqual([p["id"] for p in pend], [jogs[1]["id"]])
        r = self.chamar("post", f"/partidas/{partida['id']}/avaliacoes", {**corpo, "comentario": "Craque"}, j1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.chamar("post", f"/partidas/{partida['id']}/avaliacoes", {**corpo, "nota": 4}, j1).status_code, 409)
        self.chamar("post", f"/partidas/{partida['id']}/avaliacoes", {**corpo, "nota": 3}, o)

        perfil = self.chamar("get", f"/jogadores/{jogs[1]['id']}", token=j1).get_json()
        self.assertEqual((perfil["notaMedia"], perfil["totalAvaliacoes"]), (4.0, 2))
        avals = self.chamar("get", f"/jogadores/{jogs[1]['id']}/avaliacoes", token=j1).get_json()
        self.assertEqual(avals["meta"]["total"], 2)
        minhas = self.chamar("get", "/partidas/minhas", token=j1).get_json()["dados"]
        self.assertEqual([p["status"] for p in minhas], ["ENCERRADA"])

    def test_busca_de_jogadores_so_para_criadores_com_filtros(self):
        org = self.cadastrar("organizador", 1)
        self.cadastrar("jogador", 1)
        self.cadastrar("jogador", 2, cidade="Araguari")
        r = self.chamar("get", "/jogadores?cidade=uberlândia&posicao=FIXO&sort=notaMedia:desc", token=org["accessToken"])
        self.assertEqual([j["cidade"] for j in r.get_json()["dados"]], ["Uberlândia"])
        self.assertEqual(self.chamar("get", "/jogadores?notaMinima=4", token=org["accessToken"]).get_json()["meta"]["total"], 0)

    def test_perfis_e_quadras(self):
        q = self.cadastrar("quadra", 1)
        jog = self.cadastrar("jogador", 1)
        self.assertEqual(self.chamar("patch", "/quadras/eu", {"precoHora": 200, "tipo": "coberta"}, q["accessToken"]).get_json()["precoHora"], 200.0)
        self.assertEqual(self.chamar("patch", "/quadras/eu", {"precoHora": -1}, q["accessToken"]).status_code, 400)
        lista = self.chamar("get", "/quadras?tipo=coberta", token=jog["accessToken"]).get_json()
        self.assertEqual(lista["meta"]["total"], 1)
        self.assertEqual(self.chamar("get", f"/quadras/{q['id']}", token=jog["accessToken"]).status_code, 200)
        ok = self.chamar("patch", "/jogadores/eu", {"posicoes": [{"posicao": "PIVO", "principal": True}]}, jog["accessToken"])
        self.assertEqual(ok.get_json()["posicoes"], [{"posicao": "PIVO", "principal": True}])
        ruim = self.chamar("patch", "/jogadores/eu", {"posicoes": []}, jog["accessToken"])
        self.assertEqual(ruim.status_code, 400)
        self.assertEqual(self.chamar("patch", "/usuarios/eu", {"nome": "Novo Nome"}, jog["accessToken"]).get_json()["nome"], "Novo Nome")

    def test_edicao_e_cancelamento_pela_api(self):
        org, outro = self.cadastrar("organizador", 1), self.cadastrar("organizador", 2)
        pid = self.chamar("post", "/partidas", dados_partida(self.relogio), org["accessToken"]).get_json()["id"]
        self.assertEqual(self.chamar("patch", f"/partidas/{pid}", {"titulo": "X"}, outro["accessToken"]).status_code, 403)
        self.assertEqual(self.chamar("patch", f"/partidas/{pid}", {"titulo": "Novo"}, org["accessToken"]).get_json()["titulo"], "Novo")
        self.assertEqual(self.chamar("patch", f"/partidas/{pid}", {"totalVagas": 99}, org["accessToken"]).status_code, 400)
        self.assertEqual(self.chamar("post", f"/partidas/{pid}/cancelamento", token=org["accessToken"]).get_json()["status"], "CANCELADA")
        self.assertEqual(self.chamar("patch", f"/partidas/{pid}", {"titulo": "Y"}, org["accessToken"]).status_code, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
