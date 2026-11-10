import unittest
from decimal import Decimal

import matchmaking as mm
from jogador import Jogador
from posicao import Posicao as P

D = Decimal


def pts(posicoes=(P.ALA,), bairro_j="Centro", nota=0, total=0, jogadas=0, pedidas=frozenset({P.PIVO}), bairro_p="Outro"):
    return mm.pontuar(list(posicoes), bairro_j, D(str(nota)), total, jogadas, pedidas, bairro_p)


class TestPontuacao(unittest.TestCase):
    """Cada critério isolado: novato (15 de nota) é a linha de base."""
    BASE = D("15.00")

    def test_posicao_principal_vale_40(self):
        self.assertEqual(pts(pedidas={P.ALA}), self.BASE + 40)

    def test_posicao_secundaria_vale_20(self):
        self.assertEqual(pts(posicoes=(P.FIXO, P.ALA), pedidas={P.ALA}), self.BASE + 20)

    def test_sem_posicao_definida_vale_20_para_todos(self):
        self.assertEqual(pts(pedidas=()), self.BASE + 20)
        self.assertEqual(pts(posicoes=(P.GOLEIRO,), pedidas=()), self.BASE + 20)

    def test_sem_posicao_compativel_vale_0(self):
        self.assertEqual(pts(pedidas={P.PIVO}), self.BASE)

    def test_mesmo_bairro_vale_20_sem_diferenciar_caixa(self):
        self.assertEqual(pts(bairro_j="centro", bairro_p="CENTRO"), self.BASE + 20)
        self.assertEqual(pts(bairro_j=None, bairro_p=None), self.BASE)

    def test_nota_proporcional_a_30(self):
        self.assertEqual(pts(nota=5, total=3), D("30.00"))
        self.assertEqual(pts(nota=4, total=10), D("24.00"))
        self.assertEqual(pts(nota=0, total=3), D("0.00"))

    def test_novato_recebe_15_fixos(self):
        self.assertEqual(pts(nota=5, total=2), D("15.00"))

    def test_historico_2_por_partida_ate_10(self):
        self.assertEqual(pts(jogadas=3), self.BASE + 6)
        self.assertEqual(pts(jogadas=5), self.BASE + 10)
        self.assertEqual(pts(jogadas=20), self.BASE + 10)

    def test_maximo_e_100(self):
        self.assertEqual(pts(nota=5, total=9, jogadas=9, pedidas={P.ALA}, bairro_p="Centro"), D("100.00"))

    def test_funcao_e_pura(self):
        self.assertEqual(pts(nota=4, total=5, jogadas=2), pts(nota=4, total=5, jogadas=2))


class TestSelecao(unittest.TestCase):
    def test_limite_3x_vagas_maximo_30(self):
        self.assertEqual(mm.limite_de_propostas(2), 6)
        self.assertEqual(mm.limite_de_propostas(10), 30)
        self.assertEqual(mm.limite_de_propostas(30), 30)

    def test_escolhe_melhores_e_desempata_por_nota_depois_nome(self):
        def j(nome, nota):
            x = Jogador(nome, f"{nome}@t.com", "senha1234", "Uberlândia", [{"posicao": "ALA", "principal": True}])
            for _ in range(3):
                x.registrar_avaliacao(nota)
            return x
        ana, bia, caio = j("Ana", 3), j("Bia", 5), j("Caio", 3)
        escolhidos = mm.escolher_melhores([(ana, D(50)), (bia, D(50)), (caio, D(70))], 1)
        self.assertEqual([x.nome for x, _ in escolhidos], ["Caio", "Bia", "Ana"])

    def test_posicao_pedida_exige_ao_menos_uma(self):
        self.assertTrue(mm.tem_posicao_pedida([P.ALA], set()))
        self.assertTrue(mm.tem_posicao_pedida([P.ALA, P.FIXO], {P.FIXO}))
        self.assertFalse(mm.tem_posicao_pedida([P.ALA], {P.GOLEIRO}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
