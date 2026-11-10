import unittest
from datetime import timedelta
from decimal import Decimal

from erros import ConflitoError, DadosInvalidosError
from jogador import Jogador
from partida import Partida, StatusPartida
from organizador import Organizador
from proposta import Proposta, StatusProposta
from usuario import Papel, Usuario
from util_testes import BASE


def pos(*nomes):
    return [{"posicao": n, "principal": i == 0} for i, n in enumerate(nomes)]


def jogador(**extras):
    dados = dict(nome="Ana", email="Ana@Teste.com", senha="senha1234", cidade="Uberlândia",
                 posicoes=pos("ALA"))
    dados.update(extras)
    return Jogador(**dados)


def partida(**extras):
    org = Organizador("Org", "o@teste.com", "senha1234", "Uberlândia")
    dados = dict(criador=org, titulo="Racha", local_nome="Ginásio", endereco="Rua B", cidade="Uberlândia",
                 inicio=BASE + timedelta(days=1), fim=BASE + timedelta(days=1, hours=1),
                 total_vagas=4, valor_quadra=100, agora=BASE)
    dados.update(extras)
    return Partida(**dados)


class TestUsuario(unittest.TestCase):
    def test_classe_abstrata(self):
        with self.assertRaises(TypeError):
            Usuario("Ana", "a@a.com", "senha1234")

    def test_email_normalizado_em_minusculas(self):
        self.assertEqual(jogador().email, "ana@teste.com")

    def test_senha_curta_recusada(self):
        with self.assertRaises(DadosInvalidosError):
            jogador(senha="1234567")

    def test_senha_nao_fica_em_texto_puro_e_confere(self):
        j = jogador()
        self.assertTrue(j.verificar_senha("senha1234"))
        self.assertFalse(j.verificar_senha("outra-senha"))
        self.assertNotIn("senha_hash", j.dados_basicos())
        self.assertNotIn(b"senha1234", j._senha_hash)

    def test_papel_vem_da_subclasse(self):
        self.assertEqual(jogador().papel, Papel.JOGADOR)


class TestJogador(unittest.TestCase):
    def test_principal_fica_primeiro(self):
        j = jogador(posicoes=[{"posicao": "ALA"}, {"posicao": "PIVO", "principal": True}])
        self.assertEqual([p.value for p in j.posicoes], ["PIVO", "ALA"])

    def test_posicoes_invalidas(self):
        for ruim in ([], pos("ALA", "ALA"), pos("ALA", "FIXO", "PIVO", "GOLEIRO", "ALA"),
                     [{"posicao": "ALA"}], [{"posicao": "X", "principal": True}],
                     [{"posicao": "ALA", "principal": True}, {"posicao": "FIXO", "principal": True}]):
            with self.assertRaises(DadosInvalidosError, msg=str(ruim)):
                jogador(posicoes=ruim)

    def test_nota_media_com_arredondamento(self):
        j = jogador()
        for nota in (5, 4, 4):
            j.registrar_avaliacao(nota)
        self.assertEqual(j.nota_media, Decimal("4.33"))
        self.assertEqual(j.total_avaliacoes, 3)

    def test_nota_fora_da_faixa(self):
        with self.assertRaises(DadosInvalidosError):
            jogador().registrar_avaliacao(6)

    def test_novato_nao_e_barrado_pela_nota_minima(self):
        j = jogador()
        j.registrar_avaliacao(1); j.registrar_avaliacao(1)
        self.assertTrue(j.atende_nota_minima(Decimal("4")))
        j.registrar_avaliacao(1)
        self.assertFalse(j.atende_nota_minima(Decimal("4")))

    def test_perfil_publico_sem_dados_privados(self):
        publico = jogador().perfil_publico()
        for campo in ("email", "telefone", "senha", "senha_hash"):
            self.assertNotIn(campo, publico)


class TestPartida(unittest.TestCase):
    def test_inicio_no_passado(self):
        with self.assertRaises(DadosInvalidosError):
            partida(inicio=BASE - timedelta(hours=1), fim=BASE)

    def test_duracao_maxima_de_4_horas(self):
        inicio = BASE + timedelta(days=1)
        with self.assertRaises(DadosInvalidosError):
            partida(inicio=inicio, fim=inicio + timedelta(hours=4, minutes=1))
        partida(inicio=inicio, fim=inicio + timedelta(hours=4))

    def test_vagas_entre_2_e_30(self):
        for vagas in (1, 31):
            with self.assertRaises(DadosInvalidosError):
                partida(total_vagas=vagas)

    def test_soma_das_posicoes_nao_passa_das_vagas(self):
        with self.assertRaises(DadosInvalidosError):
            partida(total_vagas=4, posicoes=[{"posicao": "ALA", "quantidade": 3}, {"posicao": "FIXO", "quantidade": 2}])

    def test_valor_negativo(self):
        with self.assertRaises(DadosInvalidosError):
            partida(valor_quadra=-1)

    def test_maquina_de_estados(self):
        p = partida()
        p.completar(); self.assertEqual(p.status, StatusPartida.COMPLETA)
        p.reabrir(); self.assertEqual(p.status, StatusPartida.ABERTA)
        p.iniciar(p.inicio); self.assertEqual(p.status, StatusPartida.EM_ANDAMENTO)
        p.encerrar(); self.assertEqual(p.status, StatusPartida.ENCERRADA)

    def test_transicoes_invalidas(self):
        p = partida()
        with self.assertRaises(ConflitoError):
            p.encerrar()
        with self.assertRaises(ConflitoError):
            p.reabrir()
        with self.assertRaises(ConflitoError):
            p.iniciar(p.inicio - timedelta(minutes=1))
        p.cancelar()
        for acao in (p.completar, p.cancelar, p.encerrar, lambda: p.iniciar(p.inicio)):
            with self.assertRaises(ConflitoError):
                acao()

    def test_edicao_so_com_partida_aberta_e_vagas_nao_abaixo_das_aprovadas(self):
        p = partida()
        with self.assertRaises(DadosInvalidosError):
            p.editar({"total_vagas": 2}, aprovadas=3, agora=BASE)
        p.editar({"total_vagas": 6, "titulo": "Novo"}, aprovadas=3, agora=BASE)
        self.assertEqual((p.total_vagas, p.titulo), (6, "Novo"))
        p.completar()
        with self.assertRaises(ConflitoError):
            p.editar({"titulo": "X"}, aprovadas=0, agora=BASE)

    def test_edicao_invalida_nao_altera_nada(self):
        p = partida()
        with self.assertRaises(DadosInvalidosError):
            p.editar({"titulo": "Outro", "valor_quadra": -5}, aprovadas=0, agora=BASE)
        self.assertEqual(p.titulo, "Racha")

    def test_sobreposicao_de_horario(self):
        a = partida()
        b = partida(inicio=a.fim - timedelta(minutes=10), fim=a.fim + timedelta(minutes=50))
        c = partida(inicio=a.fim, fim=a.fim + timedelta(hours=1))
        self.assertTrue(a.sobrepoe(b))
        self.assertFalse(a.sobrepoe(c))


class TestProposta(unittest.TestCase):
    def test_expira_no_inicio_ou_quando_partida_deixa_de_estar_aberta(self):
        p = partida(); j = jogador()
        prop = Proposta(p, j, 80)
        self.assertFalse(prop.expirar_se_preciso(p.inicio - timedelta(minutes=1)))
        self.assertTrue(prop.expirar_se_preciso(p.inicio))
        outra = Proposta(p, j, 80)
        p.cancelar()
        self.assertTrue(outra.expirar_se_preciso(BASE))

    def test_resposta_so_em_estado_nao_final(self):
        prop = Proposta(partida(), jogador(), 50)
        prop.visualizar(); self.assertEqual(prop.status, StatusProposta.VISUALIZADA)
        prop.aceitar()
        for acao in (prop.aceitar, prop.recusar, prop.visualizar):
            with self.assertRaises(ConflitoError):
                acao()


if __name__ == "__main__":
    unittest.main(verbosity=2)
