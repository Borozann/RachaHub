# Futsal Match — Matchmaking de Futsal

Projeto didático de POO em Python: plataforma web para montar partidas de futsal ("Tinder de futebol").
Reaproveita a estrutura do projeto **AutoCenter Pro** (`oficina-mecanica`, de Cleidson Daniel,
Faculdade Anhanguera Uberlândia): módulos planos com uma classe de domínio por arquivo, API Flask,
front-end em `static/` e testes com `unittest`. Os dados ficam em memória.

## Funcionalidades
- Cadastro e login de **Jogador**, **Organizador** e **Quadra** (token de acesso de 15 min + refresh rotativo).
- Jogador com posições (1 a 4, uma principal), foto (JPEG/PNG/WebP até 2 MB) e nota média de 1 a 5.
- Criação e edição de partidas, com máquina de estados (aberta, completa, em andamento, encerrada, cancelada).
- **Matchmaking**: ao criar a partida (ou sob demanda) o sistema gera propostas para jogadores compatíveis.
  Receber uma proposta não inscreve ninguém; o jogador aceita (vira candidatura) ou recusa.
- Candidaturas diretas ou vindas de proposta, com aprovação/rejeição pelo criador e controle de vagas.
- Avaliações após a partida e recálculo da nota média.
- Busca de partidas (cidade, bairro, datas, posição, valor, status) e de jogadores (cidade, bairro, posição, nota).
- Front-end escuro com destaque verde, tema claro/escuro, header "liquid glass" e pilha de cartões com gesto.

## Requisitos
Python 3.10 ou superior e Flask (`pip install -r requirements.txt`).

## Executar
```bash
pip install -r requirements.txt
python app.py
```
Acesse `http://127.0.0.1:5000`. Ao subir, o servidor já carrega dados de demonstração.

**Contas de demonstração** (senha `senha1234`):

| Perfil | E-mail |
|---|---|
| Jogador (com propostas esperando) | `jogador1@demo.com` (há também `jogador2` a `jogador30`) |
| Organizador | `organizador1@demo.com`, `organizador2@demo.com` |
| Quadra | `quadra@demo.com` |

Roteiro rápido: entre como `jogador1`, aceite uma proposta na tela inicial; saia, entre como
`organizador1`, abra a partida em **Gerenciar** e aprove a candidatura; encerre a partida pela aba
**Ações** e avalie os jogadores.

## Testes
```bash
python -m unittest -v
```
São 89 testes: domínio, pontuação do matchmaking (um teste por critério), regras de negócio
(incluindo aprovação concorrente da última vaga), contrato HTTP e o fluxo completo
cadastro → partida → matchmaking → aceite → aprovação → encerramento → avaliação.

## Arquivos
- `usuario.py`: classe abstrata `Usuario` (senha com scrypt, e-mail normalizado).
- `jogador.py`, `organizador.py`, `quadra.py`: subclasses de `Usuario`.
- `posicao.py`: enum `Posicao`.
- `partida.py`: `Partida` e `StatusPartida` (máquina de estados).
- `candidatura.py`, `proposta.py`, `avaliacao.py`: demais entidades.
- `matchmaking.py`: elegibilidade, pontuação (função pura) e seleção.
- `plataforma.py`: guarda os dados em memória e aplica as regras entre as classes.
- `erros.py`, `validacao.py`, `paginacao.py`: exceções, validadores e paginação.
- `serializacao.py`: objetos de domínio → JSON.
- `app.py` + `static/`: API Flask e front-end (HTML/CSS/JS).
- `demo.py`: dados de demonstração.
- `test_*.py` e `util_testes.py`: testes.
- `documentacao.md`: regras, diagrama de classes e endpoints. `FRONTEND.md`: como o front-end foi feito.

## Conceitos de POO
Classes e objetos, encapsulamento (properties com validação), abstração (`Usuario`), herança
(`Jogador`, `Organizador`, `Quadra`), polimorfismo (`papel` e `perfil_completo` por subclasse),
associação (partida ↔ candidatura ↔ jogador), enums, máquina de estados e exceções de domínio.

## Limitações conhecidas
- Dados em memória: reiniciar o servidor apaga tudo (e as fotos enviadas ficam em `uploads/`).
- O refresh token fica em `localStorage` no navegador, o que o expõe a XSS; o access token fica só em memória.
- Sem pagamento, notificações, chat, geolocalização nem recuperação de senha.
- Servidor de desenvolvimento do Flask: não use em produção.
