import threading
import unittest

from candidatura import StatusCandidatura as SC
from erros import (ConflitoError, DadosInvalidosError, NaoAutenticadoError,
                   PermissaoNegadaError, RegraNegocioError)
from partida import StatusPartida as SP
from proposta import StatusProposta as SPr
from util_testes import (SENHA, dados_partida, nova_plataforma, nova_quadra,
                         novo_jogador, novo_organizador)


class Base(unittest.TestCase):
    def setUp(self):
        self.p, self.relogio = nova_plataforma()
        self.org = novo_organizador(self.p)

    def partida(self, **extras):
        return self.p.criar_partida(self.org, dados_partida(self.relogio, **extras))

    def aprovar(self, partida, jogador):
        c = self.p.candidatar(jogador, partida.id)
        return self.p.aprovar_candidatura(self.org, c.id)

    def encerrar(self, partida):
        self.relogio.agora = partida.inicio
        self.p.iniciar_partida(self.org, partida.id)
        self.p.encerrar_partida(self.org, partida.id)


class TestCadastroEAuth(Base):
    def test_email_unico_sem_diferenciar_caixa(self):
        novo_jogador(self.p, 1)
        with self.assertRaises(ConflitoError) as ctx:
            self.p.cadastrar_jogador({"nome": "X", "email": "J1@TESTE.com", "senha": SENHA,
                                      "cidade": "A", "posicoes": [{"posicao": "ALA", "principal": True}]})
        self.assertEqual(ctx.exception.codigo, "EMAIL_JA_CADASTRADO")

    def test_cadastro_invalido_nao_cria_usuario(self):
        total = len(self.p.usuarios)
        with self.assertRaises(DadosInvalidosError):
            self.p.cadastrar_jogador({"nome": "X", "email": "x@x.com", "senha": SENHA,
                                      "cidade": "A", "posicoes": []})
        self.assertEqual(len(self.p.usuarios), total)

    def test_login_refresh_rotativo_e_logout(self):
        j = novo_jogador(self.p, 1)
        t = self.p.login("j1@teste.com", SENHA)
        self.assertEqual(self.p.autenticar(t["accessToken"]).id, j.id)
        novo = self.p.renovar(t["refreshToken"])
        with self.assertRaises(NaoAutenticadoError):
            self.p.renovar(t["refreshToken"])  # refresh usado não vale mais
        with self.assertRaises(NaoAutenticadoError):
            self.p.autenticar(t["accessToken"])
        self.p.logout(j, novo["refreshToken"])
        with self.assertRaises(NaoAutenticadoError):
            self.p.autenticar(novo["accessToken"])

    def test_login_com_senha_errada(self):
        novo_jogador(self.p, 1)
        with self.assertRaises(NaoAutenticadoError):
            self.p.login("j1@teste.com", "errada123")

    def test_access_token_expira_em_15_minutos(self):
        novo_jogador(self.p, 1)
        t = self.p.login("j1@teste.com", SENHA)
        self.relogio.avancar(minutes=14)
        self.p.autenticar(t["accessToken"])
        self.relogio.avancar(minutes=2)
        with self.assertRaises(NaoAutenticadoError):
            self.p.autenticar(t["accessToken"])


class TestPartidas(Base):
    def test_quadra_usa_o_proprio_local(self):
        q = nova_quadra(self.p)
        pt = self.p.criar_partida(q, dados_partida(self.relogio, localNome="Outro", cidade="Outra"))
        self.assertEqual((pt.local_nome, pt.cidade, pt.quadra.id), ("Arena", "Uberlândia", q.id))

    def test_jogador_nao_cria_partida(self):
        with self.assertRaises(PermissaoNegadaError):
            self.p.criar_partida(novo_jogador(self.p, 1), dados_partida(self.relogio))

    def test_so_o_criador_edita_e_cancela(self):
        pt = self.partida()
        outro = novo_organizador(self.p, 2)
        with self.assertRaises(PermissaoNegadaError):
            self.p.editar_partida(outro, pt.id, {"titulo": "X"})
        with self.assertRaises(PermissaoNegadaError):
            self.p.cancelar_partida(outro, pt.id)

    def test_edicao_nao_deixa_vagas_abaixo_das_aprovadas(self):
        pt = self.partida(totalVagas=4)
        for n in range(3):
            self.aprovar(pt, novo_jogador(self.p, n))
        with self.assertRaises(DadosInvalidosError):
            self.p.editar_partida(self.org, pt.id, {"totalVagas": 2})
        self.p.editar_partida(self.org, pt.id, {"totalVagas": 5})

    def test_transicoes_invalidas_retornam_conflito(self):
        pt = self.partida()
        with self.assertRaises(ConflitoError):
            self.p.encerrar_partida(self.org, pt.id)
        with self.assertRaises(ConflitoError):  # antes do horário
            self.p.iniciar_partida(self.org, pt.id)
        self.p.cancelar_partida(self.org, pt.id)
        with self.assertRaises(ConflitoError):
            self.p.cancelar_partida(self.org, pt.id)

    def test_cancelar_expira_propostas_e_cancela_candidaturas(self):
        j0, j1, j2 = (novo_jogador(self.p, n) for n in range(3))
        pt = self.partida()
        pendente = self.p.candidatar(j0, pt.id)
        aprovada = self.aprovar(pt, j1)
        self.assertEqual(len(self.p.listar_propostas(j2, "ENVIADA")), 1)
        self.p.cancelar_partida(self.org, pt.id)
        self.assertEqual(pendente.status, SC.CANCELADA)
        self.assertEqual(aprovada.status, SC.CANCELADA)
        self.assertEqual(self.p.listar_propostas(j2, "ENVIADA"), [])
        self.assertEqual(len(self.p.listar_propostas(j2, "EXPIRADA")), 1)

    def test_filtros_de_listagem(self):
        self.partida(titulo="A", valorQuadra=50, bairro="Centro")
        self.partida(titulo="B", valorQuadra=300, bairro="Tibery", dias=3,
                     posicoes=[{"posicao": "GOLEIRO", "quantidade": 1}])
        from paginacao import Paginacao
        pag = lambda: Paginacao(permitidos=("inicio",), padrao="inicio")
        titulos = lambda f: [x.titulo for x in self.p.listar_partidas(f, pag())["dados"]]
        self.assertEqual(titulos({"valorMaximo": "100"}), ["A"])
        self.assertEqual(titulos({"bairro": "tibery"}), ["B"])
        self.assertEqual(titulos({"posicao": "goleiro"}), ["B"])
        self.assertEqual(titulos({"status": "CANCELADA"}), [])
        with self.assertRaises(DadosInvalidosError):
            titulos({"status": "XYZ"})


class TestCandidaturas(Base):
    def test_candidatura_duplicada_retorna_conflito(self):
        pt, j = self.partida(), novo_jogador(self.p, 1)
        self.p.candidatar(j, pt.id)
        with self.assertRaises(ConflitoError) as ctx:
            self.p.candidatar(j, pt.id)
        self.assertEqual(ctx.exception.codigo, "CANDIDATURA_DUPLICADA")

    def test_so_partida_aberta_recebe_candidatura(self):
        pt = self.partida(totalVagas=2)
        self.aprovar(pt, novo_jogador(self.p, 1)); self.aprovar(pt, novo_jogador(self.p, 2))
        self.assertEqual(pt.status, SP.COMPLETA)
        with self.assertRaises(ConflitoError):
            self.p.candidatar(novo_jogador(self.p, 3), pt.id)

    def test_conflito_de_horario_retorna_regra_de_negocio(self):
        j = novo_jogador(self.p, 1)
        a = self.partida(hora=20, duracao=2)
        b = self.partida(hora=21, duracao=1, titulo="Sobreposta")
        self.aprovar(a, j)
        with self.assertRaises(RegraNegocioError) as ctx:
            self.p.candidatar(j, b.id)
        self.assertEqual(ctx.exception.codigo, "CONFLITO_HORARIO")

    def test_candidatura_so_pendente_nao_bloqueia_outra_partida(self):
        j = novo_jogador(self.p, 1)
        a, b = self.partida(hora=20), self.partida(hora=20, titulo="Mesma hora")
        self.p.candidatar(j, a.id)
        self.p.candidatar(j, b.id)

    def test_nota_minima_e_excecao_para_novatos(self):
        pt = self.partida(notaMinima=4)
        novato, veterano = novo_jogador(self.p, 1), novo_jogador(self.p, 2)
        for _ in range(3):
            veterano.registrar_avaliacao(2)
        self.p.candidatar(novato, pt.id)
        with self.assertRaises(RegraNegocioError):
            self.p.candidatar(veterano, pt.id)

    def test_aprovar_ultima_vaga_completa_e_cancelar_reabre(self):
        pt = self.partida(totalVagas=2)
        j1, j2 = novo_jogador(self.p, 1), novo_jogador(self.p, 2)
        self.aprovar(pt, j1)
        self.assertEqual(pt.status, SP.ABERTA)
        c2 = self.aprovar(pt, j2)
        self.assertEqual((pt.status, self.p.vagas_restantes(pt)), (SP.COMPLETA, 0))
        self.p.cancelar_candidatura(j2, c2.id)
        self.assertEqual((pt.status, self.p.vagas_restantes(pt)), (SP.ABERTA, 1))

    def test_aprovacao_sem_vagas_retorna_conflito(self):
        pt = self.partida(totalVagas=2)
        pendente = self.p.candidatar(novo_jogador(self.p, 9), pt.id)
        self.aprovar(pt, novo_jogador(self.p, 1)); self.aprovar(pt, novo_jogador(self.p, 2))
        with self.assertRaises(ConflitoError) as ctx:
            self.p.aprovar_candidatura(self.org, pendente.id)
        self.assertEqual(ctx.exception.codigo, "PARTIDA_SEM_VAGAS")

    def test_aprovacao_concorrente_da_ultima_vaga(self):
        for rodada in range(15):
            pt = self.partida(totalVagas=2, dias=2 + rodada, titulo=f"R{rodada}")
            self.aprovar(pt, novo_jogador(self.p, f"a{rodada}"))
            pendentes = [self.p.candidatar(novo_jogador(self.p, f"b{rodada}{k}"), pt.id) for k in range(2)]
            barreira, resultados = threading.Barrier(2), []

            def aprovar(cand):
                barreira.wait()
                try:
                    self.p.aprovar_candidatura(self.org, cand.id)
                    resultados.append("ok")
                except ConflitoError:
                    resultados.append("conflito")

            threads = [threading.Thread(target=aprovar, args=(c,)) for c in pendentes]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertCountEqual(resultados, ["ok", "conflito"])
            self.assertEqual(len(self.p.aprovadas(pt)), 2)

    def test_usuario_nao_mexe_em_recurso_de_outro(self):
        pt, dono, outro = self.partida(), novo_jogador(self.p, 1), novo_jogador(self.p, 2)
        cand = self.p.candidatar(dono, pt.id)
        org2 = novo_organizador(self.p, 2)
        with self.assertRaises(PermissaoNegadaError):
            self.p.aprovar_candidatura(org2, cand.id)
        with self.assertRaises(PermissaoNegadaError):
            self.p.rejeitar_candidatura(org2, cand.id)
        with self.assertRaises(PermissaoNegadaError):
            self.p.cancelar_candidatura(outro, cand.id)
        with self.assertRaises(PermissaoNegadaError):
            self.p.listar_candidaturas_partida(org2, pt.id)

    def test_candidatura_decidida_nao_muda_de_novo(self):
        pt, j = self.partida(), novo_jogador(self.p, 1)
        cand = self.p.candidatar(j, pt.id)
        self.p.rejeitar_candidatura(self.org, cand.id)
        with self.assertRaises(ConflitoError):
            self.p.aprovar_candidatura(self.org, cand.id)


class TestPropostasEMatchmaking(Base):
    def test_criar_partida_dispara_matchmaking_so_para_elegiveis(self):
        mesma = novo_jogador(self.p, 1)
        novo_jogador(self.p, 2, cidade="Araguari")
        goleiro = novo_jogador(self.p, 3, posicoes=("GOLEIRO",))
        pt = self.partida(posicoes=[{"posicao": "GOLEIRO", "quantidade": 1}])
        donos = {x.jogador.id for x in self.p.propostas.values() if x.partida.id == pt.id}
        self.assertEqual(donos, {goleiro.id})
        self.assertNotIn(mesma.id, donos)

    def test_nao_repete_proposta_nem_propoe_a_quem_ja_se_candidatou(self):
        novo_jogador(self.p, 1), novo_jogador(self.p, 2)
        pt = self.partida()
        self.assertEqual(len(self.p.propostas), 2)
        self.assertEqual(self.p.gerar_matchmaking(self.org, pt.id), [])
        candidato, recem_chegado = novo_jogador(self.p, 3), novo_jogador(self.p, 4)
        self.p.candidatar(candidato, pt.id)
        novas = self.p.gerar_matchmaking(self.org, pt.id)
        self.assertEqual([x.jogador.id for x in novas], [recem_chegado.id])

    def test_quem_tem_aprovacao_sobreposta_nao_recebe_proposta(self):
        j = novo_jogador(self.p, 1)
        a = self.partida(hora=20, duracao=2)
        self.aprovar(a, j)
        b = self.partida(hora=21, duracao=1, titulo="Sobreposta")
        self.assertFalse([x for x in self.p.propostas.values() if x.partida.id == b.id])

    def test_limite_de_propostas_3x_vagas(self):
        for n in range(20):
            novo_jogador(self.p, n)
        pt = self.partida(totalVagas=2)
        self.assertEqual(len([x for x in self.p.propostas.values() if x.partida.id == pt.id]), 6)

    def test_aceite_cria_candidatura_vinculada(self):
        j = novo_jogador(self.p, 1)
        pt = self.partida()
        prop = self.p.listar_propostas(j)[0]
        self.p.visualizar_proposta(j, prop.id)
        cand = self.p.aceitar_proposta(j, prop.id)
        self.assertEqual((prop.status, cand.status, cand.proposta.id, cand.partida.id),
                         (SPr.ACEITA, SC.PENDENTE, prop.id, pt.id))
        self.assertEqual(cand.posicao, j.posicao_principal)

    def test_recusa_nao_cria_candidatura(self):
        j = novo_jogador(self.p, 1)
        self.partida()
        prop = self.p.listar_propostas(j)[0]
        self.p.recusar_proposta(j, prop.id)
        self.assertEqual(prop.status, SPr.RECUSADA)
        self.assertEqual(self.p.minhas_candidaturas(j), [])

    def test_so_o_dono_responde_e_proposta_expirada_nao_aceita(self):
        j, outro = novo_jogador(self.p, 1), novo_jogador(self.p, 2)
        pt = self.partida()
        prop = next(x for x in self.p.listar_propostas(j))
        with self.assertRaises(PermissaoNegadaError):
            self.p.aceitar_proposta(outro, prop.id)
        self.relogio.agora = pt.inicio
        with self.assertRaises(ConflitoError) as ctx:
            self.p.aceitar_proposta(j, prop.id)
        self.assertEqual(ctx.exception.codigo, "PROPOSTA_EXPIRADA")
        self.assertEqual(prop.status, SPr.EXPIRADA)

    def test_aceite_que_viola_regra_nao_altera_a_proposta(self):
        j = novo_jogador(self.p, 1)
        a = self.partida(hora=20, duracao=2)
        b = self.partida(hora=21, duracao=1, titulo="Sobreposta")
        prop_b = next(x for x in self.p.listar_propostas(j) if x.partida.id == b.id)
        self.aprovar(a, j)
        with self.assertRaises(RegraNegocioError):
            self.p.aceitar_proposta(j, prop_b.id)
        self.assertEqual(prop_b.status, SPr.ENVIADA)
        self.assertEqual([c for c in self.p.minhas_candidaturas(j) if c.partida.id == b.id], [])

    def test_proposta_expira_quando_partida_deixa_de_estar_aberta(self):
        j = novo_jogador(self.p, 1)
        pt = self.partida(totalVagas=2)
        prop = self.p.listar_propostas(j)[0]
        self.aprovar(pt, novo_jogador(self.p, 2)); self.aprovar(pt, novo_jogador(self.p, 3))
        self.assertEqual(pt.status, SP.COMPLETA)
        self.assertEqual(self.p.listar_propostas(j)[0].status, SPr.EXPIRADA)
        self.assertEqual(prop.status, SPr.EXPIRADA)

    def test_matchmaking_so_do_criador_e_em_partida_aberta(self):
        pt = self.partida()
        with self.assertRaises(PermissaoNegadaError):
            self.p.gerar_matchmaking(novo_organizador(self.p, 2), pt.id)
        self.p.cancelar_partida(self.org, pt.id)
        with self.assertRaises(ConflitoError):
            self.p.gerar_matchmaking(self.org, pt.id)


class TestAvaliacoes(Base):
    def setUp(self):
        super().setUp()
        self.j1, self.j2, self.fora = (novo_jogador(self.p, n) for n in (1, 2, 3))
        self.pt = self.partida()
        self.aprovar(self.pt, self.j1); self.aprovar(self.pt, self.j2)

    def test_so_depois_de_encerrada(self):
        with self.assertRaises(ConflitoError):
            self.p.avaliar(self.org, self.pt.id, self.j1.id, 5)

    def test_quem_nao_participou_recebe_403(self):
        self.encerrar(self.pt)
        with self.assertRaises(PermissaoNegadaError):
            self.p.avaliar(self.fora, self.pt.id, self.j1.id, 5)
        with self.assertRaises(PermissaoNegadaError):
            self.p.avaliar(novo_organizador(self.p, 2), self.pt.id, self.j1.id, 5)
        with self.assertRaises(PermissaoNegadaError):
            self.p.avaliacoes_pendentes(self.fora, self.pt.id)

    def test_avaliacao_recalcula_nota_media(self):
        self.encerrar(self.pt)
        self.p.avaliar(self.org, self.pt.id, self.j1.id, 5)
        self.p.avaliar(self.j2, self.pt.id, self.j1.id, 4)
        self.assertEqual((float(self.j1.nota_media), self.j1.total_avaliacoes), (4.5, 2))

    def test_unicidade_autoavaliacao_e_avaliado_invalido(self):
        self.encerrar(self.pt)
        self.p.avaliar(self.j1, self.pt.id, self.j2.id, 3)
        with self.assertRaises(ConflitoError):
            self.p.avaliar(self.j1, self.pt.id, self.j2.id, 5)
        with self.assertRaises(DadosInvalidosError):
            self.p.avaliar(self.j1, self.pt.id, self.j1.id, 5)
        with self.assertRaises(RegraNegocioError):
            self.p.avaliar(self.j1, self.pt.id, self.fora.id, 5)
        with self.assertRaises(DadosInvalidosError):
            self.p.avaliar(self.j2, self.pt.id, self.j1.id, 9)
        self.assertEqual(self.j2.total_avaliacoes, 1)

    def test_pendentes_diminuem_conforme_avalia(self):
        self.encerrar(self.pt)
        self.assertCountEqual([j.id for j in self.p.avaliacoes_pendentes(self.org, self.pt.id)], [self.j1.id, self.j2.id])
        self.assertEqual([j.id for j in self.p.avaliacoes_pendentes(self.j1, self.pt.id)], [self.j2.id])
        self.p.avaliar(self.org, self.pt.id, self.j1.id, 4)
        self.assertEqual([j.id for j in self.p.avaliacoes_pendentes(self.org, self.pt.id)], [self.j2.id])

    def test_historico_de_partidas_aumenta_pontuacao_de_matchmaking(self):
        self.encerrar(self.pt)
        self.assertEqual(self.p._partidas_jogadas(self.j1), 1)
        self.assertEqual(self.p._partidas_jogadas(self.fora), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
