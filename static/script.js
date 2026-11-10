"use strict";
const API = "/api";
const estado = { usuario: null, acesso: null };
const POSICOES = { GOLEIRO: "Goleiro", FIXO: "Fixo", ALA: "Ala", PIVO: "Pivô" };
const STATUS_ROTULO = {
  ABERTA: "Aberta", COMPLETA: "Completa", EM_ANDAMENTO: "Em andamento", ENCERRADA: "Encerrada",
  CANCELADA: "Cancelada", PENDENTE: "Pendente", APROVADA: "Aprovada", REJEITADA: "Rejeitada",
  ENVIADA: "Enviada", VISUALIZADA: "Vista", ACEITA: "Aceita", RECUSADA: "Recusada", EXPIRADA: "Expirada",
};
const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];
const principal = $("#principal");

const esc = (valor) =>
  String(valor ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const moeda = (v) => Number(v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const dataHora = (iso) =>
  new Date(iso).toLocaleString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const ehCriador = () => estado.usuario && estado.usuario.papel !== "JOGADOR";

class ErroApi extends Error {
  constructor(mensagem, codigo, status) {
    super(mensagem);
    this.codigo = codigo;
    this.status = status;
  }
}

/* ===== Toasts e modal ===== */
function aviso(mensagem, erro = false) {
  const el = document.createElement("div");
  el.className = `toast${erro ? " erro" : ""}`;
  el.textContent = mensagem;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 4200);
}

function confirmar(titulo, texto, rotulo = "Confirmar") {
  const modal = $("#modal");
  modal.innerHTML = `<h3>${esc(titulo)}</h3><p>${esc(texto)}</p>
    <div class="linha"><button class="btn btn-sutil" value="nao">Voltar</button>
    <button class="btn btn-perigo" value="sim">${esc(rotulo)}</button></div>`;
  return new Promise((resolver) => {
    modal.onclick = (e) => {
      const botao = e.target.closest("button");
      if (botao) { modal.close(); resolver(botao.value === "sim"); }
    };
    modal.oncancel = () => resolver(false);
    modal.showModal();
  });
}

/* ===== Cliente HTTP com refresh automático ===== */
let renovando = null;
function renovarSessao() {
  const refresh = localStorage.getItem("refreshToken");
  if (!refresh) return Promise.reject(new ErroApi("Sem sessão.", "NAO_AUTENTICADO", 401));
  if (!renovando) {
    renovando = fetch(`${API}/auth/refresh`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refreshToken: refresh }),
    })
      .then(async (r) => {
        if (!r.ok) throw new ErroApi("Sessão expirada.", "NAO_AUTENTICADO", 401);
        guardarTokens(await r.json());
      })
      .finally(() => { renovando = null; });
  }
  return renovando;
}

function guardarTokens(t) {
  estado.acesso = t.accessToken;
  localStorage.setItem("refreshToken", t.refreshToken);
}

async function api(metodo, caminho, corpo, jaTentou = false) {
  const opcoes = { method: metodo, headers: {} };
  if (estado.acesso) opcoes.headers.Authorization = `Bearer ${estado.acesso}`;
  if (corpo instanceof FormData) opcoes.body = corpo;
  else if (corpo !== undefined) { opcoes.headers["Content-Type"] = "application/json"; opcoes.body = JSON.stringify(corpo); }
  const resp = await fetch(API + caminho, opcoes);
  if (resp.status === 401 && !jaTentou && !caminho.startsWith("/auth/")) {
    try { await renovarSessao(); } catch (e) { encerrarSessaoLocal(); throw e; }
    return api(metodo, caminho, corpo, true);
  }
  if (resp.status === 204) return null;
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new ErroApi(dados.mensagem || "Algo deu errado.", dados.codigo, resp.status);
  return dados;
}

function encerrarSessaoLocal() {
  estado.usuario = null;
  estado.acesso = null;
  localStorage.removeItem("refreshToken");
  desenharNavegacao();
  location.hash = "#/login";
}

/* ===== Navegação ===== */
const MENU_JOGADOR = [
  ["#/propostas", "fa-fire", "Propostas"], ["#/buscar", "fa-magnifying-glass", "Buscar"],
  ["#/candidaturas", "fa-list-check", "Candidaturas"], ["#/minhas-partidas", "fa-futbol", "Partidas"],
  ["#/perfil", "fa-user", "Perfil"],
];
const MENU_CRIADOR = [
  ["#/minhas-partidas", "fa-futbol", "Partidas"], ["#/criar", "fa-plus", "Criar"],
  ["#/jogadores", "fa-users", "Jogadores"], ["#/perfil", "fa-user", "Perfil"],
];

function desenharNavegacao() {
  const itens = !estado.usuario ? [] : estado.usuario.papel === "JOGADOR" ? MENU_JOGADOR : MENU_CRIADOR;
  const atual = location.hash.split("/").slice(0, 2).join("/");
  $("#navDesktop").innerHTML = itens
    .map(([h, , nome]) => `<a href="${h}" ${atual === h ? 'aria-current="page"' : ""}>${nome}</a>`).join("");
  $("#navMobile").innerHTML = itens
    .map(([h, icone, nome]) => `<a href="${h}" ${atual === h ? 'aria-current="page"' : ""}><i class="fa-solid ${icone}"></i>${nome}</a>`).join("");
  $("#btnSair").hidden = !estado.usuario;
}

const inicioDoPapel = () => (estado.usuario?.papel === "JOGADOR" ? "#/propostas" : "#/minhas-partidas");
let acoes = {};
let versaoRota = 0;

const ROTAS = [
  [/^#?\/?$/, null, telaLanding],
  [/^#\/login$/, null, telaLogin],
  [/^#\/cadastro$/, null, telaCadastro],
  [/^#\/propostas$/, ["JOGADOR"], telaPropostas],
  [/^#\/buscar$/, ["JOGADOR"], telaBuscarPartidas],
  [/^#\/candidaturas$/, ["JOGADOR"], telaCandidaturas],
  [/^#\/partida\/([\w-]+)$/, "auth", telaDetalhe],
  [/^#\/minhas-partidas$/, "auth", telaMinhasPartidas],
  [/^#\/perfil$/, "auth", telaPerfil],
  [/^#\/criar$/, ["ORGANIZADOR", "QUADRA"], () => telaFormPartida(null)],
  [/^#\/editar\/([\w-]+)$/, ["ORGANIZADOR", "QUADRA"], telaFormPartida],
  [/^#\/gerenciar\/([\w-]+)$/, ["ORGANIZADOR", "QUADRA"], telaGerenciar],
  [/^#\/jogadores$/, ["ORGANIZADOR", "QUADRA"], telaBuscarJogadores],
  [/^#\/avaliar\/([\w-]+)$/, "auth", telaAvaliar],
];

function rotear() {
  versaoRota += 1;
  acoes = {};
  const hash = location.hash || "#/";
  for (const [regex, permitidos, tela] of ROTAS) {
    const m = hash.match(regex);
    if (!m) continue;
    if (permitidos && !estado.usuario) { location.hash = "#/login"; return; }
    if (Array.isArray(permitidos) && !permitidos.includes(estado.usuario.papel)) { location.hash = inicioDoPapel(); return; }
    if (!permitidos && estado.usuario && /^#?\/?(login|cadastro)?$/.test(hash)) { location.hash = inicioDoPapel(); return; }
    desenharNavegacao();
    principal.focus({ preventScroll: true });
    tela(m[1]);
    return;
  }
  location.hash = "#/";
}

async function tela(buscar, desenhar) {
  const versao = versaoRota;
  principal.innerHTML = '<div class="grade"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
  try {
    const dados = await buscar();
    if (versao !== versaoRota) return;
    desenhar(dados);
  } catch (e) {
    if (versao !== versaoRota) return;
    principal.innerHTML = `<div class="vazio erro-estado" role="alert"><i class="fa-solid fa-triangle-exclamation"></i>
      <p>${esc(e.message)}</p><button class="btn btn-sutil" data-acao="repetir">Tentar de novo</button></div>`;
    acoes.repetir = () => rotear();
  }
}

principal.addEventListener("click", (e) => {
  const alvo = e.target.closest("[data-acao]");
  if (alvo && acoes[alvo.dataset.acao]) acoes[alvo.dataset.acao](alvo, e);
});

function aoEnviar(seletor, tratar) {
  const form = $(seletor);
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const botao = $('button[type="submit"]', form);
    botao.disabled = true;
    try { await tratar(Object.fromEntries(new FormData(form)), form); }
    catch (erro) { aviso(erro.message, true); }
    finally { botao.disabled = false; }
  });
}

/* ===== Componentes de UI ===== */
const badge = (s) => `<span class="badge badge-${esc(s)}">${esc(STATUS_ROTULO[s] || s)}</span>`;
const iniciais = (nome) => nome.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
const avatar = (j, grande = false) => j.fotoUrl
  ? `<img class="avatar${grande ? " avatar-g" : ""}" src="${esc(j.fotoUrl)}" alt="Foto de ${esc(j.nome)}">`
  : `<span class="avatar${grande ? " avatar-g" : ""}" aria-hidden="true">${esc(iniciais(j.nome))}</span>`;
const notaHtml = (j) => j.totalAvaliacoes
  ? `<span class="nota"><i class="fa-solid fa-star" aria-hidden="true"></i>${j.notaMedia.toFixed(1)} <small>(${j.totalAvaliacoes})</small></span>`
  : '<span class="muted">Sem avaliações</span>';
const chipsPosicoes = (lista) => (lista || [])
  .map((p) => `<span class="chip ${p.principal ? "chip-principal" : ""}">${esc(POSICOES[p.posicao])}${p.principal ? " ★" : ""}</span>`).join(" ");

function vazio(icone, texto) {
  return `<div class="vazio"><i class="fa-solid ${icone}"></i><p>${esc(texto)}</p></div>`;
}

function cartaoPartida(p, extra = "") {
  const pct = Math.round((p.vagasPreenchidas / p.totalVagas) * 100);
  const pedidas = p.posicoes.map((x) => `<span class="chip">${x.quantidade}× ${esc(POSICOES[x.posicao])}</span>`).join(" ");
  return `<article class="card card-partida">
    <div class="linha" style="justify-content:space-between">
      <h3><a href="#/partida/${esc(p.id)}">${esc(p.titulo)}</a></h3>${badge(p.status)}</div>
    <div class="meta">
      <span><i class="fa-regular fa-calendar" aria-hidden="true"></i>${esc(dataHora(p.inicio))}</span>
      <span><i class="fa-solid fa-location-dot" aria-hidden="true"></i>${esc(p.localNome)}${p.bairro ? ` · ${esc(p.bairro)}` : ""} · ${esc(p.cidade)}</span>
      <span><i class="fa-solid fa-sack-dollar" aria-hidden="true"></i>${moeda(p.valorQuadra)}</span>
      ${p.notaMinima !== null ? `<span><i class="fa-solid fa-star" aria-hidden="true"></i>nota mín. ${p.notaMinima}</span>` : ""}
    </div>
    ${pedidas ? `<div>${pedidas}</div>` : ""}
    <div class="progresso" role="progressbar" aria-label="Vagas preenchidas" aria-valuemin="0" aria-valuemax="${p.totalVagas}" aria-valuenow="${p.vagasPreenchidas}"><div style="width:${pct}%"></div></div>
    <small class="muted">${p.vagasPreenchidas}/${p.totalVagas} vagas preenchidas</small>
    ${extra}</article>`;
}

function seletorPosicao(jogador, nome = "posicao") {
  const opcoes = (jogador.posicoes || []).map((p) => `<option value="${esc(p.posicao)}">${esc(POSICOES[p.posicao])}</option>`).join("");
  return `<label>Posição em que quer jogar<select name="${nome}">${opcoes}</select></label>`;
}

function camposPosicoes(selecionadas = []) {
  const mapa = Object.fromEntries(selecionadas.map((p) => [p.posicao, p]));
  const linhas = Object.entries(POSICOES).map(([cod, nome]) => `
    <div class="linha"><label class="opcao"><input type="checkbox" name="pos" value="${cod}" ${mapa[cod] ? "checked" : ""}> ${nome}</label>
    <label class="opcao"><input type="radio" name="principal" value="${cod}" ${mapa[cod]?.principal ? "checked" : ""}> principal</label></div>`).join("");
  return `<fieldset><legend>Posições (1 a 4, uma principal)</legend>${linhas}</fieldset>`;
}

function lerPosicoes(form) {
  const marcadas = $$('input[name="pos"]:checked', form).map((i) => i.value);
  const principalMarcada = $('input[name="principal"]:checked', form)?.value;
  if (!marcadas.length) throw new Error("Escolha ao menos uma posição.");
  if (!principalMarcada || !marcadas.includes(principalMarcada)) throw new Error("Marque uma posição principal entre as escolhidas.");
  return marcadas.map((posicao) => ({ posicao, principal: posicao === principalMarcada }));
}

function paginacaoHtml(meta) {
  const paginas = Math.max(Math.ceil(meta.total / meta.limit), 1);
  if (paginas <= 1) return "";
  return `<nav class="paginacao" aria-label="Paginação">
    <button class="btn btn-sutil btn-pequeno" data-acao="pagina" data-pagina="${meta.page - 1}" ${meta.page <= 1 ? "disabled" : ""}>Anterior</button>
    <span>Página ${meta.page} de ${paginas}</span>
    <button class="btn btn-sutil btn-pequeno" data-acao="pagina" data-pagina="${meta.page + 1}" ${meta.page >= paginas ? "disabled" : ""}>Próxima</button></nav>`;
}

const consulta = (dados, extras = {}) => {
  const params = new URLSearchParams();
  Object.entries({ ...dados, ...extras }).forEach(([k, v]) => { if (v !== "" && v != null) params.set(k, v); });
  return params.toString();
};

/* ===== Telas públicas ===== */
function telaLanding() {
  principal.innerHTML = `<section class="hero">
    <h1>Encontre o <span>time</span> certo para o seu futsal</h1>
    <p>Jogadores recebem propostas de partidas compatíveis, organizadores e quadras preenchem as vagas com quem combina.</p>
    <div class="linha" style="justify-content:center">
      <a class="btn" href="#/cadastro"><i class="fa-solid fa-user-plus"></i> Criar conta</a>
      <a class="btn btn-sutil" href="#/login"><i class="fa-solid fa-right-to-bracket"></i> Entrar</a></div>
    <p class="muted espaco"><small>Demonstração: jogador1@demo.com, organizador1@demo.com ou quadra@demo.com — senha senha1234</small></p>
  </section>`;
}

function telaLogin() {
  principal.innerHTML = `<div class="card" style="max-width:420px;margin:0 auto"><h1>Entrar</h1>
    <form id="formLogin"><label>E-mail<input name="email" type="email" autocomplete="username" required></label>
    <label>Senha<input name="senha" type="password" autocomplete="current-password" required></label>
    <button class="btn btn-bloco" type="submit">Entrar</button></form>
    <p class="espaco muted">Ainda não tem conta? <a href="#/cadastro">Cadastre-se</a></p></div>`;
  aoEnviar("#formLogin", async (d) => { await entrar(d.email, d.senha); });
}

async function entrar(email, senha) {
  guardarTokens(await api("POST", "/auth/login", { email, senha }));
  estado.usuario = await api("GET", "/usuarios/eu");
  location.hash = inicioDoPapel();
  rotear();
}

const PAPEIS = {
  JOGADOR: ["fa-person-running", "Jogador", "Receba propostas e entre em partidas."],
  ORGANIZADOR: ["fa-clipboard-user", "Organizador", "Crie partidas e monte o time."],
  QUADRA: ["fa-warehouse", "Quadra", "Publique horários na sua quadra."],
};

function telaCadastro() {
  principal.innerHTML = `<h1>Criar conta</h1><p class="muted">Passo 1 de 2 — como você vai usar o Futsal Match?</p>
    <div class="papeis">${Object.entries(PAPEIS).map(([cod, [icone, nome, texto]]) => `
      <button class="card papel-card" data-acao="papel" data-papel="${cod}"><i class="fa-solid ${icone}"></i><h3>${nome}</h3><span class="muted">${texto}</span></button>`).join("")}</div>`;
  acoes.papel = (el) => formularioCadastro(el.dataset.papel);
}

function formularioCadastro(papel) {
  const comuns = `<div class="campos">
    <label>Nome<input name="nome" required maxlength="120"></label>
    <label>E-mail<input name="email" type="email" autocomplete="username" required></label>
    <label>Senha (mín. 8)<input name="senha" type="password" minlength="8" autocomplete="new-password" required></label>
    <label>Telefone<input name="telefone" type="tel" maxlength="20"></label>`;
  const extras = {
    JOGADOR: `<label>Cidade<input name="cidade" required maxlength="80"></label><label>Bairro<input name="bairro" maxlength="80"></label></div>${camposPosicoes()}`,
    ORGANIZADOR: `<label>Cidade<input name="cidade" required maxlength="80"></label></div>`,
    QUADRA: `<label>Nome fantasia<input name="nomeFantasia" required maxlength="120"></label>
      <label>Endereço<input name="endereco" required maxlength="200"></label>
      <label>Cidade<input name="cidade" required maxlength="80"></label><label>Bairro<input name="bairro" maxlength="80"></label>
      <label>Tipo<input name="tipo" maxlength="40" placeholder="society, coberta..."></label>
      <label>Preço por hora (R$)<input name="precoHora" type="number" min="0" step="0.01"></label></div>`,
  };
  principal.innerHTML = `<h1>Cadastro de ${PAPEIS[papel][1].toLowerCase()}</h1><p class="muted">Passo 2 de 2</p>
    <form id="formCadastro">${comuns}${extras[papel]}
    <div class="linha"><button type="button" class="btn btn-sutil" data-acao="voltar">Voltar</button><button class="btn" type="submit">Criar conta</button></div></form>`;
  acoes.voltar = () => telaCadastro();
  aoEnviar("#formCadastro", async (d, form) => {
    const corpo = { ...d };
    delete corpo.pos; delete corpo.principal;
    if (papel === "JOGADOR") corpo.posicoes = lerPosicoes(form);
    if (corpo.precoHora === "") delete corpo.precoHora;
    await api("POST", `/auth/cadastro/${papel.toLowerCase()}`, corpo);
    aviso("Conta criada!");
    await entrar(d.email, d.senha);
  });
}

/* ===== Jogador: propostas (pilha de cartões) ===== */
const vistas = new Set();

function telaPropostas() {
  tela(() => api("GET", "/propostas"), (res) => {
    let fila = res.dados.filter((p) => p.status === "ENVIADA" || p.status === "VISUALIZADA");
    let ocupado = false;
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>Propostas</h1><span class="muted" id="contador"></span></div>
      <p class="muted dica">Arraste para a direita para aceitar (vira candidatura) ou para a esquerda para recusar. Também funciona com as setas do teclado.</p>
      <div class="pilha" id="pilha" aria-label="Pilha de propostas"></div><div class="acoes-carta" id="acoesCarta"></div>`;

    const desenhar = () => {
      $("#contador").textContent = fila.length ? `${fila.length} proposta(s)` : "";
      const pilha = $("#pilha");
      if (!fila.length) {
        pilha.innerHTML = vazio("fa-inbox", "Sem propostas no momento. Busque partidas abertas ou volte mais tarde.");
        $("#acoesCarta").innerHTML = '<a class="btn" href="#/buscar">Buscar partidas</a>';
        return;
      }
      $("#acoesCarta").innerHTML = `<button class="btn-icone btn-nao" data-acao="recusar" aria-label="Recusar proposta"><i class="fa-solid fa-xmark"></i></button>
        <button class="btn-icone btn-sim" data-acao="aceitar" aria-label="Aceitar proposta"><i class="fa-solid fa-check"></i></button>`;
      pilha.innerHTML = fila.slice(0, 3).map((p, i) => {
        const pt = p.partida;
        return `<article class="carta glass ${i === 0 ? "topo" : ""}" data-id="${esc(p.id)}" ${i === 0 ? 'tabindex="0"' : ""}
          style="${i ? `transform:scale(${1 - i * 0.05}) translateY(${i * 14}px);z-index:${10 - i}` : "z-index:10"}">
          <span class="selo selo-sim" aria-hidden="true">ENTRAR</span><span class="selo selo-nao" aria-hidden="true">PASSO</span>
          <h2>${esc(pt.titulo)}</h2>
          <div class="meta" style="flex-direction:column">
            <span><i class="fa-regular fa-calendar"></i>${esc(dataHora(pt.inicio))}</span>
            <span><i class="fa-solid fa-location-dot"></i>${esc(pt.localNome)}${pt.bairro ? ` · ${esc(pt.bairro)}` : ""}</span>
            <span><i class="fa-solid fa-sack-dollar"></i>${moeda(pt.valorQuadra)} (quadra)</span>
            <span><i class="fa-solid fa-user-group"></i>${pt.vagasRestantes} vaga(s) de ${pt.totalVagas}</span></div>
          <div>${pt.posicoes.map((x) => `<span class="chip">${x.quantidade}× ${esc(POSICOES[x.posicao])}</span>`).join(" ")}</div>
          ${i === 0 ? seletorPosicao(estado.usuario) : ""}
          <div class="pontos"><span class="muted">Compatibilidade</span><span class="pontuacao">${Math.round(p.pontuacao)}</span></div></article>`;
      }).join("");
      const topo = $(".carta.topo");
      if (!vistas.has(fila[0].id)) { vistas.add(fila[0].id); api("POST", `/propostas/${fila[0].id}/visualizacao`).catch(() => {}); }
      ligarArrasto(topo);
      topo.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight") decidir("aceitar");
        if (e.key === "ArrowLeft") decidir("recusar");
      });
    };

    async function decidir(acao) {
      if (ocupado || !fila.length) return;
      ocupado = true;
      const topo = $(".carta.topo");
      const proposta = fila[0];
      try {
        if (acao === "aceitar") {
          await api("POST", `/propostas/${proposta.id}/aceite`, { posicao: $("select", topo)?.value });
          aviso("Candidatura enviada! Aguarde a aprovação do organizador.");
        } else {
          await api("POST", `/propostas/${proposta.id}/recusa`);
        }
        topo.style.transform = `translateX(${acao === "aceitar" ? 600 : -600}px) rotate(${acao === "aceitar" ? 20 : -20}deg)`;
        topo.style.opacity = "0";
        fila.shift();
        setTimeout(() => { ocupado = false; desenhar(); }, 220);
      } catch (e) {
        aviso(e.message, true);
        topo.style.transform = "";
        if (["PROPOSTA_EXPIRADA", "PROPOSTA_FINALIZADA", "PARTIDA_FECHADA", "CANDIDATURA_DUPLICADA"].includes(e.codigo)) fila.shift();
        ocupado = false;
        desenhar();
      }
    }

    function ligarArrasto(carta) {
      let x0 = null, dx = 0;
      const [sim, nao] = [$(".selo-sim", carta), $(".selo-nao", carta)];
      carta.addEventListener("pointerdown", (e) => {
        if (e.target.closest("select, button")) return;
        x0 = e.clientX; carta.setPointerCapture(e.pointerId); carta.classList.add("arrastando");
      });
      carta.addEventListener("pointermove", (e) => {
        if (x0 === null) return;
        dx = e.clientX - x0;
        carta.style.transform = `translateX(${dx}px) rotate(${dx / 20}deg)`;
        sim.style.opacity = dx > 0 ? Math.min(dx / 100, 1) : 0;
        nao.style.opacity = dx < 0 ? Math.min(-dx / 100, 1) : 0;
      });
      const soltar = () => {
        if (x0 === null) return;
        carta.classList.remove("arrastando");
        const passou = Math.abs(dx) > 100;
        const direcao = dx > 0 ? "aceitar" : "recusar";
        x0 = null; dx = 0;
        if (passou) { decidir(direcao); return; }
        carta.style.transform = ""; sim.style.opacity = 0; nao.style.opacity = 0;
      };
      carta.addEventListener("pointerup", soltar);
      carta.addEventListener("pointercancel", soltar);
    }

    acoes.aceitar = () => decidir("aceitar");
    acoes.recusar = () => decidir("recusar");
    desenhar();
  });
}

/* ===== Buscas ===== */
function telaBuscarPartidas() {
  const posicoes = Object.entries(POSICOES).map(([c, n]) => `<option value="${c}">${n}</option>`).join("");
  principal.innerHTML = `<div class="cabecalho-pagina"><h1>Buscar partidas</h1></div>
    <form id="filtros" class="card"><div class="campos">
      <label>Cidade<input name="cidade" value="${esc(estado.usuario.cidade)}"></label>
      <label>Bairro<input name="bairro"></label>
      <label>De<input name="dataDe" type="date"></label><label>Até<input name="dataAte" type="date"></label>
      <label>Posição<select name="posicao"><option value="">Qualquer</option>${posicoes}</select></label>
      <label>Valor máximo (R$)<input name="valorMaximo" type="number" min="0" step="0.01"></label>
      <label>Status<select name="status"><option value="ABERTA">Abertas</option><option value="">Todas</option></select></label>
      </div><button class="btn" type="submit"><i class="fa-solid fa-filter"></i> Filtrar</button></form>
    <div id="resultado" class="grade espaco"></div>`;
  let pagina = 1;
  const buscar = async () => {
    const dados = Object.fromEntries(new FormData($("#filtros")));
    const alvo = $("#resultado");
    alvo.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
    try {
      const res = await api("GET", `/partidas?${consulta(dados, { page: pagina, limit: 8 })}`);
      alvo.innerHTML = res.dados.length
        ? res.dados.map((p) => cartaoPartida(p, p.status === "ABERTA" ? `<div><a class="btn btn-pequeno" href="#/partida/${esc(p.id)}">Ver e candidatar</a></div>` : "")).join("") + paginacaoHtml(res.meta)
        : vazio("fa-magnifying-glass", "Nenhuma partida encontrada com esses filtros.");
    } catch (e) { alvo.innerHTML = `<div class="vazio erro-estado" role="alert">${esc(e.message)}</div>`; }
  };
  aoEnviar("#filtros", async () => { pagina = 1; await buscar(); });
  acoes.pagina = (el) => { pagina = Number(el.dataset.pagina); buscar(); };
  buscar();
}

function telaBuscarJogadores() {
  const posicoes = Object.entries(POSICOES).map(([c, n]) => `<option value="${c}">${n}</option>`).join("");
  principal.innerHTML = `<div class="cabecalho-pagina"><h1>Buscar jogadores</h1></div>
    <form id="filtros" class="card"><div class="campos">
      <label>Cidade<input name="cidade" value="${esc(estado.usuario.cidade)}"></label><label>Bairro<input name="bairro"></label>
      <label>Posição<select name="posicao"><option value="">Qualquer</option>${posicoes}</select></label>
      <label>Nota mínima<input name="notaMinima" type="number" min="0" max="5" step="0.1"></label>
      <label>Ordenar por<select name="sort"><option value="nome:asc">Nome</option><option value="notaMedia:desc">Melhor nota</option></select></label>
      </div><button class="btn" type="submit"><i class="fa-solid fa-filter"></i> Filtrar</button></form>
    <div id="resultado" class="grade grade-2 espaco"></div>`;
  let pagina = 1;
  const buscar = async () => {
    const alvo = $("#resultado");
    alvo.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
    try {
      const res = await api("GET", `/jogadores?${consulta(Object.fromEntries(new FormData($("#filtros"))), { page: pagina, limit: 10 })}`);
      alvo.innerHTML = res.dados.length
        ? res.dados.map((j) => `<article class="card linha">${avatar(j)}<div><h3>${esc(j.nome)}</h3>
            <div class="meta"><span>${esc(j.cidade)}${j.bairro ? ` · ${esc(j.bairro)}` : ""}</span>${notaHtml(j)}</div>
            <div>${chipsPosicoes(j.posicoes)}</div></div></article>`).join("") + `<div style="grid-column:1/-1">${paginacaoHtml(res.meta)}</div>`
        : `<div style="grid-column:1/-1">${vazio("fa-user-slash", "Nenhum jogador encontrado.")}</div>`;
    } catch (e) { alvo.innerHTML = `<div class="vazio erro-estado" role="alert">${esc(e.message)}</div>`; }
  };
  aoEnviar("#filtros", async () => { pagina = 1; await buscar(); });
  acoes.pagina = (el) => { pagina = Number(el.dataset.pagina); buscar(); };
  buscar();
}

/* ===== Detalhe da partida ===== */
function telaDetalhe(id) {
  tela(async () => {
    const [partida, part] = await Promise.all([api("GET", `/partidas/${id}`), api("GET", `/partidas/${id}/participantes`)]);
    let minha = null;
    if (estado.usuario.papel === "JOGADOR") {
      minha = (await api("GET", "/candidaturas")).dados.find((c) => c.partida.id === id) || null;
    }
    return { partida, participantes: part.dados, minha };
  }, ({ partida: p, participantes, minha }) => {
    let acao = "";
    if (estado.usuario.papel === "JOGADOR") {
      if (minha) {
        acao = `<p>Sua candidatura: ${badge(minha.status)}</p>` + (["PENDENTE", "APROVADA"].includes(minha.status)
          ? `<button class="btn btn-perigo" data-acao="cancelarCand">Cancelar candidatura</button>` : "");
      } else if (p.status === "ABERTA") {
        acao = `<form id="formCand">${seletorPosicao(estado.usuario)}<button class="btn" type="submit"><i class="fa-solid fa-hand"></i> Candidatar-se</button></form>`;
      } else acao = '<p class="muted">Esta partida não está recebendo candidaturas.</p>';
    } else if (p.criador.id === estado.usuario.id) {
      acao = `<a class="btn" href="#/gerenciar/${esc(p.id)}">Gerenciar partida</a>`;
    }
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>${esc(p.titulo)}</h1>${badge(p.status)}</div>
      ${cartaoPartida(p)}
      ${p.descricao ? `<div class="card espaco"><h3>Sobre</h3><p>${esc(p.descricao)}</p><p class="muted">Endereço: ${esc(p.endereco)}</p><p class="muted">Criada por ${esc(p.criador.nome)}</p></div>` : `<p class="muted espaco">Endereço: ${esc(p.endereco)} · Criada por ${esc(p.criador.nome)}</p>`}
      <div class="card espaco">${acao}</div>
      <h2 class="espaco">Participantes (${participantes.length})</h2>
      ${participantes.length ? `<div class="grade grade-2">${participantes.map((j) => `<div class="card linha">${avatar(j)}<div><strong>${esc(j.nome)}</strong><div>${notaHtml(j)}</div></div></div>`).join("")}</div>` : vazio("fa-user-group", "Ainda não há jogadores aprovados.")}`;
    aoEnviar("#formCand", async (d) => {
      await api("POST", `/partidas/${id}/candidaturas`, { posicao: d.posicao });
      aviso("Candidatura enviada!");
      rotear();
    });
    acoes.cancelarCand = async () => {
      if (!(await confirmar("Cancelar candidatura?", "Sua vaga será liberada.", "Cancelar candidatura"))) return;
      try { await api("POST", `/candidaturas/${minha.id}/cancelamento`); aviso("Candidatura cancelada."); rotear(); }
      catch (e) { aviso(e.message, true); }
    };
  });
}

/* ===== Jogador: candidaturas e partidas ===== */
function telaCandidaturas() {
  const abas = [["", "Todas"], ["PENDENTE", "Pendentes"], ["APROVADA", "Aprovadas"], ["REJEITADA", "Rejeitadas"], ["CANCELADA", "Canceladas"]];
  let ativa = "";
  principal.innerHTML = `<div class="cabecalho-pagina"><h1>Minhas candidaturas</h1></div>
    <div class="abas" role="tablist">${abas.map(([v, n]) => `<button role="tab" data-acao="aba" data-valor="${v}" aria-selected="${v === ativa}">${n}</button>`).join("")}</div>
    <div id="lista" class="grade"></div>`;
  const carregar = async () => {
    $$(".abas button").forEach((b) => b.setAttribute("aria-selected", b.dataset.valor === ativa));
    const alvo = $("#lista");
    alvo.innerHTML = '<div class="skeleton"></div>';
    try {
      const res = await api("GET", `/candidaturas${ativa ? `?status=${ativa}` : ""}`);
      alvo.innerHTML = res.dados.length ? res.dados.map((c) => cartaoPartida(c.partida, `<div class="linha">${badge(c.status)}
        ${["PENDENTE", "APROVADA"].includes(c.status) ? `<button class="btn btn-perigo btn-pequeno" data-acao="cancelar" data-id="${esc(c.id)}">Cancelar</button>` : ""}</div>`)).join("")
        : vazio("fa-clipboard-list", "Nenhuma candidatura por aqui.");
    } catch (e) { alvo.innerHTML = `<div class="vazio erro-estado" role="alert">${esc(e.message)}</div>`; }
  };
  acoes.aba = (el) => { ativa = el.dataset.valor; carregar(); };
  acoes.cancelar = async (el) => {
    if (!(await confirmar("Cancelar candidatura?", "Se estiver aprovada, sua vaga será liberada.", "Cancelar candidatura"))) return;
    try { await api("POST", `/candidaturas/${el.dataset.id}/cancelamento`); aviso("Candidatura cancelada."); carregar(); }
    catch (e) { aviso(e.message, true); }
  };
  carregar();
}

function telaMinhasPartidas() {
  const jogador = estado.usuario.papel === "JOGADOR";
  tela(() => api("GET", "/partidas/minhas?limit=50&sort=inicio:desc"), (res) => {
    const agora = new Date();
    const futuras = res.dados.filter((p) => new Date(p.fim) >= agora && !["ENCERRADA", "CANCELADA"].includes(p.status)).reverse();
    const passadas = res.dados.filter((p) => !futuras.includes(p));
    const extra = (p) => {
      const botoes = [];
      if (!jogador) botoes.push(`<a class="btn btn-pequeno" href="#/gerenciar/${esc(p.id)}">Gerenciar</a>`);
      if (!jogador && p.status === "ABERTA") botoes.push(`<a class="btn btn-sutil btn-pequeno" href="#/editar/${esc(p.id)}">Editar</a>`);
      if (p.status === "ENCERRADA") botoes.push(`<a class="btn btn-pequeno" href="#/avaliar/${esc(p.id)}"><i class="fa-solid fa-star"></i> Avaliar</a>`);
      return botoes.length ? `<div class="linha">${botoes.join("")}</div>` : "";
    };
    const secao = (titulo, lista, msg) => `<h2 class="espaco">${titulo}</h2><div class="grade">${lista.length ? lista.map((p) => cartaoPartida(p, extra(p))).join("") : vazio("fa-futbol", msg)}</div>`;
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>Minhas partidas</h1>
      ${jogador ? "" : '<a class="btn" href="#/criar"><i class="fa-solid fa-plus"></i> Nova partida</a>'}</div>
      ${secao("Próximas", futuras, jogador ? "Você não tem partidas aprovadas. Veja suas propostas!" : "Você ainda não criou partidas.")}
      ${secao("Passadas", passadas, "Nada por aqui ainda.")}`;
  });
}

/* ===== Criador: formulário e gerenciamento ===== */
function telaFormPartida(id) {
  tela(async () => (id ? api("GET", `/partidas/${id}`) : null), (p) => {
    const quadra = estado.usuario.papel === "QUADRA";
    const qtd = (pos) => p?.posicoes.find((x) => x.posicao === pos)?.quantidade ?? 0;
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>${p ? "Editar partida" : "Nova partida"}</h1></div>
      <form id="formPartida" class="card"><div class="campos">
        <label class="largo">Título<input name="titulo" required maxlength="120" value="${esc(p?.titulo)}"></label>
        <label class="largo">Descrição<textarea name="descricao" maxlength="2000">${esc(p?.descricao)}</textarea></label>
        ${quadra ? `<p class="muted largo">O local será o da sua quadra: ${esc(estado.usuario.nomeFantasia)} — ${esc(estado.usuario.endereco)}.</p>` : `
          <label>Nome do local<input name="localNome" required maxlength="120" value="${esc(p?.localNome)}"></label>
          <label>Endereço<input name="endereco" required maxlength="200" value="${esc(p?.endereco)}"></label>
          <label>Cidade<input name="cidade" required maxlength="80" value="${esc(p?.cidade ?? estado.usuario.cidade)}"></label>
          <label>Bairro<input name="bairro" maxlength="80" value="${esc(p?.bairro)}"></label>`}
        <label>Início<input name="inicio" type="datetime-local" required value="${esc(p?.inicio)}"></label>
        <label>Fim (máx. 4h)<input name="fim" type="datetime-local" required value="${esc(p?.fim)}"></label>
        <label>Total de vagas (2 a 30)<input name="totalVagas" type="number" min="2" max="30" required value="${esc(p?.totalVagas ?? 10)}"></label>
        <label>Valor da quadra (R$)<input name="valorQuadra" type="number" min="0" step="0.01" required value="${esc(p?.valorQuadra ?? estado.usuario.precoHora ?? "")}"></label>
        <label>Nota mínima (0 a 5)<input name="notaMinima" type="number" min="0" max="5" step="0.1" value="${esc(p?.notaMinima)}"></label>
      </div>
      <fieldset><legend>Posições necessárias (opcional)</legend><div class="campos">${Object.entries(POSICOES).map(([c, n]) =>
        `<label>${n}<input name="qtd_${c}" type="number" min="0" max="30" value="${qtd(c)}"></label>`).join("")}</div></fieldset>
      <div class="linha"><a class="btn btn-sutil" href="#/minhas-partidas">Voltar</a><button class="btn" type="submit">${p ? "Salvar alterações" : "Criar partida e buscar jogadores"}</button></div></form>`;
    aoEnviar("#formPartida", async (d) => {
      const corpo = {
        titulo: d.titulo, descricao: d.descricao || null, inicio: d.inicio, fim: d.fim,
        totalVagas: Number(d.totalVagas), valorQuadra: d.valorQuadra, notaMinima: d.notaMinima === "" ? null : d.notaMinima,
        posicoes: Object.keys(POSICOES).filter((c) => Number(d[`qtd_${c}`]) > 0).map((c) => ({ posicao: c, quantidade: Number(d[`qtd_${c}`]) })),
      };
      if (!quadra) Object.assign(corpo, { localNome: d.localNome, endereco: d.endereco, cidade: d.cidade, bairro: d.bairro || null });
      const salva = p ? await api("PATCH", `/partidas/${id}`, corpo) : await api("POST", "/partidas", corpo);
      aviso(p ? "Partida atualizada." : "Partida criada! Propostas enviadas aos jogadores compatíveis.");
      location.hash = `#/gerenciar/${salva.id}`;
    });
  });
}

function telaGerenciar(id) {
  tela(() => api("GET", `/partidas/${id}`), (p) => {
    if (p.criador.id !== estado.usuario.id) { aviso("Só o criador gerencia a partida.", true); location.hash = inicioDoPapel(); return; }
    let aba = "candidaturas";
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>${esc(p.titulo)}</h1>${badge(p.status)}</div>${cartaoPartida(p)}
      <div class="abas espaco" role="tablist">${[["candidaturas", "Candidaturas"], ["participantes", "Participantes"], ["acoesAba", "Ações"]]
        .map(([v, n]) => `<button role="tab" data-acao="aba" data-valor="${v}" aria-selected="${v === aba}">${n}</button>`).join("")}</div>
      <div id="aba" class="grade"></div>`;

    const desenharAba = async () => {
      $$(".abas button").forEach((b) => b.setAttribute("aria-selected", b.dataset.valor === aba));
      const alvo = $("#aba");
      alvo.innerHTML = '<div class="skeleton"></div>';
      try {
        if (aba === "candidaturas") {
          const res = await api("GET", `/partidas/${id}/candidaturas`);
          alvo.innerHTML = res.dados.length ? res.dados.map((c) => `<article class="card linha">${avatar(c.jogador)}
            <div style="flex:1"><h3>${esc(c.jogador.nome)}</h3><div class="meta">${notaHtml(c.jogador)}<span>${c.posicao ? esc(POSICOES[c.posicao]) : ""}</span></div></div>
            ${badge(c.status)}${c.status === "PENDENTE" ? `<div class="linha">
              <button class="btn btn-pequeno" data-acao="decidir" data-tipo="aprovacao" data-id="${esc(c.id)}">Aprovar</button>
              <button class="btn btn-perigo btn-pequeno" data-acao="decidir" data-tipo="rejeicao" data-id="${esc(c.id)}">Rejeitar</button></div>` : ""}</article>`).join("")
            : vazio("fa-inbox", "Nenhuma candidatura ainda. Rode o matchmaking na aba Ações.");
        } else if (aba === "participantes") {
          const res = await api("GET", `/partidas/${id}/participantes`);
          alvo.innerHTML = res.dados.length ? res.dados.map((j) => `<article class="card linha">${avatar(j)}<div><h3>${esc(j.nome)}</h3>${notaHtml(j)}</div></article>`).join("")
            : vazio("fa-user-group", "Nenhum jogador aprovado ainda.");
        } else {
          const aberta = ["ABERTA", "COMPLETA"].includes(p.status);
          alvo.innerHTML = `<div class="card grade">
            <button class="btn" data-acao="mm" ${p.status === "ABERTA" ? "" : "disabled"}><i class="fa-solid fa-wand-magic-sparkles"></i> Rodar matchmaking</button>
            <button class="btn btn-sutil" data-acao="fluxo" data-tipo="inicio" ${aberta ? "" : "disabled"}><i class="fa-solid fa-play"></i> Iniciar partida</button>
            <button class="btn btn-sutil" data-acao="fluxo" data-tipo="encerramento" ${p.status === "EM_ANDAMENTO" ? "" : "disabled"}><i class="fa-solid fa-flag-checkered"></i> Encerrar partida</button>
            ${p.status === "ABERTA" ? `<a class="btn btn-sutil" href="#/editar/${esc(id)}"><i class="fa-solid fa-pen"></i> Editar dados</a>` : ""}
            ${p.status === "ENCERRADA" ? `<a class="btn" href="#/avaliar/${esc(id)}"><i class="fa-solid fa-star"></i> Avaliar jogadores</a>` : ""}
            <button class="btn btn-perigo" data-acao="fluxo" data-tipo="cancelamento" ${aberta ? "" : "disabled"}><i class="fa-solid fa-ban"></i> Cancelar partida</button></div>`;
        }
      } catch (e) { alvo.innerHTML = `<div class="vazio erro-estado" role="alert">${esc(e.message)}</div>`; }
    };

    acoes.aba = (el) => { aba = el.dataset.valor; desenharAba(); };
    acoes.decidir = async (el) => {
      try { await api("POST", `/candidaturas/${el.dataset.id}/${el.dataset.tipo}`); aviso(el.dataset.tipo === "aprovacao" ? "Jogador aprovado." : "Candidatura rejeitada."); rotear(); }
      catch (e) { aviso(e.message, true); }
    };
    acoes.mm = async () => {
      try { const r = await api("POST", `/partidas/${id}/matchmaking`); aviso(`${r.propostasGeradas} nova(s) proposta(s) enviada(s).`); }
      catch (e) { aviso(e.message, true); }
    };
    acoes.fluxo = async (el) => {
      if (el.dataset.tipo === "cancelamento" && !(await confirmar("Cancelar partida?", "Candidaturas e propostas em aberto serão canceladas.", "Cancelar partida"))) return;
      try { await api("POST", `/partidas/${id}/${el.dataset.tipo}`); aviso("Partida atualizada."); rotear(); }
      catch (e) { aviso(e.message, true); }
    };
    desenharAba();
  });
}

/* ===== Avaliações ===== */
function telaAvaliar(id) {
  tela(async () => {
    const [partida, pend] = await Promise.all([api("GET", `/partidas/${id}`), api("GET", `/partidas/${id}/avaliacoes/pendentes`)]);
    return { partida, pendentes: pend.dados };
  }, ({ partida, pendentes }) => {
    const cartao = (j) => `<article class="card" data-jogador="${esc(j.id)}"><div class="linha">${avatar(j)}<h3>${esc(j.nome)}</h3></div>
      <form class="formAvaliacao" data-id="${esc(j.id)}"><div class="estrelas" role="radiogroup" aria-label="Nota para ${esc(j.nome)}">
        ${[5, 4, 3, 2, 1].map((n) => `<input type="radio" name="nota" id="n${n}-${esc(j.id)}" value="${n}" required><label for="n${n}-${esc(j.id)}" title="${n} estrela(s)"><span class="sr-only">${n} estrela(s)</span>★</label>`).join("")}</div>
        <label>Comentário (opcional)<textarea name="comentario" maxlength="500"></textarea></label>
        <button class="btn" type="submit">Enviar avaliação</button></form></article>`;
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>Avaliar jogadores</h1>${badge(partida.status)}</div><p class="muted">${esc(partida.titulo)}</p>
      <div id="avaliacoes" class="grade grade-2">${partida.status !== "ENCERRADA" ? "" : pendentes.map(cartao).join("")}</div>
      <div id="semPendentes">${partida.status !== "ENCERRADA" ? vazio("fa-hourglass-half", "A avaliação é liberada quando a partida for encerrada.") : pendentes.length ? "" : vazio("fa-circle-check", "Tudo avaliado por aqui!")}</div>`;
    $("#avaliacoes").addEventListener("submit", async (e) => {
      const form = e.target.closest(".formAvaliacao");
      if (!form) return;
      e.preventDefault();
      const d = Object.fromEntries(new FormData(form));
      try {
        await api("POST", `/partidas/${id}/avaliacoes`, { avaliadoId: form.dataset.id, nota: Number(d.nota), comentario: d.comentario || null });
        form.closest("article").remove();
        aviso("Avaliação enviada!");
        if (!$("#avaliacoes article")) $("#semPendentes").innerHTML = vazio("fa-circle-check", "Tudo avaliado por aqui!");
      } catch (erro) { aviso(erro.message, true); }
    });
  });
}

/* ===== Perfil ===== */
function telaPerfil() {
  tela(async () => {
    estado.usuario = await api("GET", "/usuarios/eu");
    const u = estado.usuario;
    return u.papel === "JOGADOR" ? (await api("GET", `/jogadores/${u.id}/avaliacoes?limit=10`)).dados : [];
  }, (avaliacoes) => {
    const u = estado.usuario;
    const cabecalho = u.papel === "JOGADOR"
      ? `<div class="card linha">${avatar(u, true)}<div><h2>${esc(u.nome)}</h2>${notaHtml(u)}<div>${chipsPosicoes(u.posicoes)}</div>
          <label class="btn btn-sutil btn-pequeno espaco" style="cursor:pointer"><i class="fa-solid fa-camera"></i> Trocar foto
          <input type="file" id="foto" accept="image/jpeg,image/png,image/webp" class="sr-only"></label></div></div>`
      : `<div class="card"><h2>${esc(u.nome)}</h2><p class="muted">${u.papel === "QUADRA" ? "Quadra" : "Organizador"} · ${esc(u.email)}</p></div>`;
    const especificos = {
      JOGADOR: `<label>Cidade<input name="cidade" required value="${esc(u.cidade)}"></label><label>Bairro<input name="bairro" value="${esc(u.bairro)}"></label></div>${camposPosicoes(u.posicoes)}`,
      ORGANIZADOR: `<label>Cidade<input name="cidade" required value="${esc(u.cidade)}"></label></div>`,
      QUADRA: `<label>Nome fantasia<input name="nomeFantasia" required value="${esc(u.nomeFantasia)}"></label><label>Endereço<input name="endereco" required value="${esc(u.endereco)}"></label>
        <label>Cidade<input name="cidade" required value="${esc(u.cidade)}"></label><label>Bairro<input name="bairro" value="${esc(u.bairro)}"></label>
        <label>Tipo<input name="tipo" value="${esc(u.tipo)}"></label><label>Preço por hora (R$)<input name="precoHora" type="number" min="0" step="0.01" value="${esc(u.precoHora)}"></label></div>`,
    };
    principal.innerHTML = `<div class="cabecalho-pagina"><h1>Perfil</h1></div>${cabecalho}
      <form id="formPerfil" class="card espaco"><div class="campos">
        <label>Nome<input name="nome" required value="${esc(u.nome)}"></label><label>Telefone<input name="telefone" value="${esc(u.telefone)}"></label>
        ${especificos[u.papel]}<button class="btn" type="submit">Salvar perfil</button></form>
      ${u.papel === "JOGADOR" ? `<h2 class="espaco">Avaliações recebidas</h2><div class="grade">${avaliacoes.length ? avaliacoes.map((a) => `<article class="card"><span class="nota">${"★".repeat(a.nota)}<small>${esc(a.avaliador.nome)} · ${esc(a.partidaTitulo)}</small></span>${a.comentario ? `<p>${esc(a.comentario)}</p>` : ""}</article>`).join("") : vazio("fa-star", "Você ainda não recebeu avaliações.")}</div>` : ""}`;
    aoEnviar("#formPerfil", async (d, form) => {
      const posicoes = u.papel === "JOGADOR" ? lerPosicoes(form) : null;
      await api("PATCH", "/usuarios/eu", { nome: d.nome, telefone: d.telefone || null });
      const base = { cidade: d.cidade, bairro: d.bairro || null };
      if (u.papel === "JOGADOR") await api("PATCH", "/jogadores/eu", { ...base, posicoes });
      if (u.papel === "ORGANIZADOR") await api("PATCH", "/organizadores/eu", { cidade: d.cidade });
      if (u.papel === "QUADRA") await api("PATCH", "/quadras/eu", { ...base, nomeFantasia: d.nomeFantasia, endereco: d.endereco, tipo: d.tipo || null, precoHora: d.precoHora || null });
      aviso("Perfil salvo.");
      rotear();
    });
    $("#foto")?.addEventListener("change", async (e) => {
      const arquivo = e.target.files[0];
      if (!arquivo) return;
      if (arquivo.size > 2 * 1024 * 1024) { aviso("A foto pode ter no máximo 2 MB.", true); return; }
      const corpo = new FormData();
      corpo.append("foto", arquivo);
      try { await api("PUT", "/jogadores/eu/foto", corpo); aviso("Foto atualizada."); rotear(); }
      catch (erro) { aviso(erro.message, true); }
    });
  });
}

/* ===== Tema e inicialização ===== */
function aplicarTema(tema) {
  document.documentElement.dataset.theme = tema;
  try { localStorage.setItem("tema", tema); } catch (e) { /* armazenamento indisponível */ }
}
(function iniciarTema() {
  let salvo = null;
  try { salvo = localStorage.getItem("tema"); } catch (e) { salvo = null; }
  aplicarTema(salvo || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
})();
$("#btnTema").addEventListener("click", () => aplicarTema(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
window.addEventListener("scroll", () => $("#topbar").classList.toggle("rolado", scrollY > 4), { passive: true });
$("#btnSair").addEventListener("click", async () => {
  try { await api("POST", "/auth/logout", { refreshToken: localStorage.getItem("refreshToken") }); } catch (e) { /* sessão já inválida */ }
  encerrarSessaoLocal();
});
window.addEventListener("hashchange", rotear);

(async function iniciar() {
  if (localStorage.getItem("refreshToken")) {
    try { await renovarSessao(); estado.usuario = await api("GET", "/usuarios/eu"); }
    catch (e) { estado.usuario = null; localStorage.removeItem("refreshToken"); }
  }
  rotear();
})();
