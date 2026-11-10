# Como o front-end foi construído — Futsal Match

## Arquitetura
Mesmo desenho do projeto original: o navegador conversa por `fetch` com a API Flask (`app.py`), e só o servidor
importa as classes de domínio.

```
Navegador (HTML/CSS/JS)  <-- HTTP/JSON -->  Flask (app.py)  -->  Plataforma  -->  Jogador / Partida / ...
```

`static/` tem `index.html` (casca com header, navegação e modal), `style.css` (tokens e componentes) e `script.js`
(rotas por `#/hash`, telas, cliente HTTP). Toda tela tem estado de carregamento (skeleton), vazio e erro.

## Cliente HTTP
O access token fica em memória e o refresh token em `localStorage` (limitação registrada no README). Ao receber 401, o
cliente renova a sessão uma única vez, mesmo com várias requisições em paralelo, e repete a chamada.

## Telas
- **Públicas**: landing, login e cadastro em 2 passos (papel → formulário).
- **Jogador**: Propostas (inicial), Buscar partidas, Detalhe, Candidaturas (abas por status), Partidas (próximas e passadas, com Avaliar) e Perfil.
- **Organizador e Quadra**: Partidas (inicial), Criar/Editar, Gerenciar (abas Candidaturas, Participantes e Ações), Buscar jogadores, Avaliar e Perfil.

## Pilha de propostas
Cada proposta é um cartão. Arrastar passando de 100 px para a direita aceita (vira candidatura) e para a esquerda
recusa; os botões abaixo e as setas do teclado (cartão focado) fazem o mesmo. Se a API recusa o aceite (por exemplo,
conflito de horário), o cartão volta ao lugar e o motivo aparece em um toast. Ao exibir o cartão, a proposta é marcada como visualizada.

## Design
Escuro por padrão, com verde de destaque; tema claro/escuro por `data-theme`, respeitando `prefers-color-scheme` e com
alternador manual. Tokens em CSS variables (cores, escala de 4 px, raios, sombras, tipografia, durações, z-index).
O efeito "liquid glass" (`backdrop-filter: blur() saturate()`, borda translúcida, brilho interno) só aparece no header, na
barra inferior (mobile), no modal e no cartão de proposta, com fallback sólido via `@supports not`. Navegação inferior no
mobile e no header a partir de 768 px. Animações curtas, desligadas com `prefers-reduced-motion`. O texto do usuário é
sempre escapado antes de entrar no HTML.

## Fora do que foi pedido
Não há React, TanStack Query nem Vitest: o front-end é JavaScript puro, como no projeto original. Os testes do front
foram feitos manualmente no navegador (login, pilha por botão, teclado e arrasto, aprovação, cadastro e temas).
