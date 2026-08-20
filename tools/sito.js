/* Comportamento del sito: ricerca, pulsante di segnalazione che segue la
   lettura, segnalazione della frase selezionata.
   Nessuna libreria esterna, nessun cookie, niente che esca dal browser. */

(function () {
  var HL1 = '@@HL@@', HL2 = '@@LH@@';
  var indice = null, curSec = '';

  /* La frase selezionata resta in memoria anche dopo che il browser ha
     chiuso la selezione: sul telefono il menu di sistema (Copia / Condividi)
     copre la bollina, quindi si segnala con il pulsante flottante e la frase
     deve essere ancora lì. Vale due minuti, e si consuma quando si usa. */
  var frasePronta = null;   // {testo, sezione, quando}
  var VALIDITA = 120000;

  function fraseInCanna() {
    if (!frasePronta) return null;
    if (Date.now() - frasePronta.quando > VALIDITA) { frasePronta = null; return null; }
    return frasePronta;
  }
  function ricorda(testo) {
    frasePronta = { testo: testo, sezione: curSec, quando: Date.now() };
    aggiornaEtichettaFab();
  }
  function dimentica() { frasePronta = null; }

  function el(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ---------------- ricerca ---------------- */

  function caricaIndice() {
    if (indice) return Promise.resolve(indice);
    return fetch((typeof BASE === 'string' ? BASE : '') + '/ricerca.json')
      .then(function (r) { return r.json(); })
      .then(function (j) { indice = j; return j; });
  }

  function mostraRisultati(q, dati) {
    var out = [];
    var ql = q.toLowerCase();
    dati.forEach(function (p) {
      var t = p.x.toLowerCase(), i = t.indexOf(ql), n = 0;
      // il titolo che corrisponde vale come primo risultato
      if (p.t.toLowerCase().indexOf(ql) > -1) {
        out.push({ p: p, frag: p.x.slice(0, 150) + '...' });
        n++;
      }
      while (i > -1 && n < 3) {
        var a = Math.max(0, i - 70), b = Math.min(p.x.length, i + q.length + 90);
        out.push({
          p: p,
          frag: (a > 0 ? '... ' : '') + p.x.slice(a, i) + HL1 + p.x.slice(i, i + q.length) +
                HL2 + p.x.slice(i + q.length, b) + (b < p.x.length ? ' ...' : '')
        });
        i = t.indexOf(ql, i + q.length); n++;
      }
    });

    var r = el('res');
    r.classList.add('on');
    el('doc').style.display = 'none';
    r.innerHTML = out.length
      ? '<h1>' + out.length + ' risultat' + (out.length === 1 ? 'o' : 'i') + ' per «' + esc(q) + '»</h1>' +
        out.map(function (o) {
          var f = esc(o.frag).split(HL1).join('<mark>').split(HL2).join('</mark>');
          return '<a class="hit" href="' + o.p.u + '"><b>' + esc(o.p.t) + '</b><span>' + f + '</span></a>';
        }).join('')
      : '<h1>Nessun risultato per «' + esc(q) + '»</h1><p>Prova con una parola sola, o con meno lettere.</p>';
  }

  function cerca(q) {
    q = q.trim();
    if (q.length < 2) {
      el('res').classList.remove('on');
      el('doc').style.display = '';
      trackSection();
      return;
    }
    el('doc').style.display = 'none';
    var r = el('res');
    r.classList.add('on');
    if (!indice) r.innerHTML = '<p class="cerca-stato">Cerco...</p>';
    caricaIndice().then(function (dati) {
      if (el('q').value.trim() === q) mostraRisultati(q, dati);
    }).catch(function () {
      r.innerHTML = '<p class="cerca-stato">La ricerca non è disponibile in questo momento.</p>';
    });
    el('fab').classList.remove('on');
  }

  /* ---------------- il pulsante segue la sezione ---------------- */

  function trackSection() {
    if (el('res').classList.contains('on')) { el('fab').classList.remove('on'); return; }
    var hs = document.querySelectorAll('#body h2'), trovata = '';
    for (var i = 0; i < hs.length; i++) {
      if (hs[i].getBoundingClientRect().top < 140) trovata = hs[i].dataset.raw;
      else break;
    }
    curSec = trovata;
    aggiornaEtichettaFab();
    el('fab').classList.toggle('on', window.scrollY > 220);
  }

  /* Il pulsante dice cosa manderà: se c'è una frase selezionata lo dichiara,
     altrimenti mostra la sezione che si sta leggendo. */
  function aggiornaEtichettaFab() {
    var pronta = fraseInCanna();
    el('fab').classList.toggle('con-frase', !!pronta);
    el('fab_s').textContent = pronta ? 'con la frase selezionata'
                                     : (curSec || 'in questa pagina');
  }

  /* ---------------- selezione del testo ---------------- */

  function hideBub() { el('bub').classList.remove('on'); }

  function leggiSelezione() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed) return null;
    var t = sel.toString().trim();
    if (t.length < 4 || !el('body').contains(sel.anchorNode)) return null;
    return t.length > 400 ? t.slice(0, 400) + '...' : t;
  }

  /* Ogni volta che c'è una selezione valida la si ricorda. Quando la
     selezione sparisce NON si dimentica: è proprio il caso del telefono. */
  function onSelectionChange() {
    var t = leggiSelezione();
    if (t) ricorda(t);
  }

  function onSelect() {
    var t = leggiSelezione();
    if (!t) { hideBub(); return; }
    ricorda(t);

    var sel = window.getSelection();
    var r = sel.getRangeAt(0).getBoundingClientRect();
    var b = el('bub');
    b.classList.add('on');

    var x = r.left + r.width / 2 + window.scrollX;
    // su schermo stretto la bollina va SOTTO la selezione: sopra ci sta il
    // menu di sistema del telefono, e si coprirebbero a vicenda
    var sotto = window.innerWidth < 900;
    var y = sotto ? r.bottom + window.scrollY + 12
                  : r.top + window.scrollY - b.offsetHeight - 10;
    b.classList.toggle('sotto', sotto);
    b.style.left = Math.max(70, Math.min(x, window.innerWidth - 70)) - b.offsetWidth / 2 + 'px';
    b.style.top = Math.max(window.scrollY + 6, y) + 'px';
  }

  /* ---------------- segnalazione ---------------- */

  /* Un clic solo: si apre il modulo Google con pagina, sezione, indirizzo e
     frase già compilati. Chi segnala scrive soltanto il commento e invia una
     volta sola. Se il modulo non è ancora collegato, si spiega cosa manca. */

  /* sez        — sezione dichiarata da chi chiama ('' = decidi tu)
     frase      — frase esplicita ('' = usa quella selezionata di recente)
     soloSuaSez — vero per i pulsanti accanto ai titoli: prendono la frase
                  solo se è stata selezionata in QUELLA sezione */
  function openSeg(sez, frase, soloSuaSez) {
    var pronta = fraseInCanna();
    if (!frase && pronta && (!soloSuaSez || pronta.sezione === sez)) {
      frase = pronta.testo;
      sez = pronta.sezione || sez;   // la frase sa da dove viene
    }
    dimentica();
    hideBub();
    aggiornaEtichettaFab();

    var dati = {
      pagina: PAGINA,
      sezione: sez || curSec || '(tutta la pagina)',
      indirizzo: location.origin + location.pathname,
      frase: frase || ''
    };

    if (!MODULO.url) { spiegaModuloMancante(dati); return; }

    var u = MODULO.url + (MODULO.url.indexOf('?') > -1 ? '&' : '?') + 'usp=pp_url';
    Object.keys(MODULO.campi).forEach(function (k) {
      if (MODULO.campi[k]) u += '&' + MODULO.campi[k] + '=' + encodeURIComponent(dati[k] || '');
    });
    window.open(u, '_blank', 'noopener');
  }

  function spiegaModuloMancante(dati) {
    el('mod').innerHTML =
      '<h3>Il modulo non è ancora collegato</h3>' +
      '<p class="lead">Il pulsante funziona, ma manca l\'indirizzo del modulo Google dove finiscono ' +
      'le segnalazioni. Si configura in <code>tools/costruisci_sito.py</code>.</p>' +
      '<div class="fld"><label>Pagina</label><div class="ro">' + esc(dati.pagina) + '</div></div>' +
      '<div class="fld"><label>Sezione</label><div class="ro">' + esc(dati.sezione) + '</div></div>' +
      (dati.frase ? '<div class="fld"><label>La frase selezionata</label>' +
                    '<div class="quoted">' + esc(dati.frase) + '</div></div>' : '') +
      '<div class="note">Nel frattempo puoi scrivere la segnalazione nel gruppo dei catechisti, ' +
      'citando la pagina e la sezione qui sopra.</div>' +
      '<div class="acts"><button class="pri" id="chiudi">Ho capito</button></div>';
    el('chiudi').onclick = closeSeg;
    el('ov').classList.add('on');
  }

  function closeSeg() { el('ov').classList.remove('on'); }

  /* ---------------- avvio ---------------- */

  window.openSeg = openSeg;
  window.closeSeg = closeSeg;

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.seg').forEach(function (b) {
      b.onclick = function () { openSeg(b.dataset.s, '', true); };
    });

    el('q').addEventListener('input', function (e) { cerca(e.target.value); });
    el('burger').onclick = function () { el('side').classList.toggle('on'); };
    el('ov').onclick = function (e) { if (e.target === el('ov')) closeSeg(); };
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { closeSeg(); hideBub(); }
    });

    el('fab').onclick = function () { openSeg('', ''); };
    el('bub').onmousedown = function (e) { e.preventDefault(); };
    el('bub').onclick = function () {
      var pronta = fraseInCanna();
      if (window.getSelection) window.getSelection().removeAllRanges();
      openSeg(pronta ? pronta.sezione : curSec, pronta ? pronta.testo : '');
    };

    // scorrendo si nasconde la bollina, ma la frase resta in memoria
    window.addEventListener('scroll', function () { trackSection(); hideBub(); }, { passive: true });
    window.addEventListener('resize', trackSection);
    document.addEventListener('mouseup', function () { setTimeout(onSelect, 10); });
    document.addEventListener('touchend', function () { setTimeout(onSelect, 10); });
    document.addEventListener('selectionchange', function () { setTimeout(onSelectionChange, 10); });

    // porta in vista la voce di menu della pagina corrente: con quasi cento
    // voci, altrimenti la barra laterale mostra sempre l'inizio dell'elenco
    var attiva = document.querySelector('#nav a.on');
    if (attiva) {
      var lato = el('side');
      var dy = attiva.offsetTop - lato.clientHeight / 2;
      if (dy > 0) lato.scrollTop = dy;
    }

    trackSection();
  });
})();
