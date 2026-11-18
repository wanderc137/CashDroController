/* Reproductor asciinema inline para CashDroController.
   Usa window.CASHDRO_CAST (eventos) y window.CASHDRO_CAST_META. */
(function () {
  'use strict';

  var EVENTS = window.CASHDRO_CAST || [];
  var META = window.CASHDRO_CAST_META || {};
  var shell = document.querySelector('.cast-shell');
  var screenEl = document.getElementById('cashdro-screen');
  var poster = document.getElementById('cast-poster');
  if (!shell || !screenEl || !EVENTS.length) return;

  var COLS = META.width || 100;
  var ROWS = META.height || 30;
  var DURATION = META.duration || (EVENTS.length ? EVENTS[EVENTS.length - 1][0] : 0);

  var COLORS = {
    30: '#1e1e1e', 31: '#ff6b6b', 32: '#14F195', 33: '#FFB020',
    34: '#79c0ff', 35: '#d2a8ff', 36: '#56d4dd', 37: '#e8edf6',
    90: '#7f8ea3', 91: '#ff8787', 92: '#7ee787', 93: '#ffd166',
    94: '#79c0ff', 95: '#d2a8ff', 96: '#56d4dd', 97: '#ffffff'
  };

  var playBtn = document.getElementById('cast-play');
  var restartBtn = document.getElementById('cast-restart');
  var copyBtn = document.getElementById('cast-copy');
  var rangeEl = document.getElementById('cast-range');
  var timeEl = document.getElementById('cast-time');
  var speedEl = document.getElementById('cast-speed');
  var fullBtn = document.getElementById('cast-full');
  var startBtn = document.getElementById('cast-start');

  var cells, cx, cy, fg, bold;
  var idx = 0;
  var elapsed = 0;
  var playing = false;
  var started = false;
  var raf = null;
  var playStart = 0;
  var playFrom = 0;
  var speed = 1;
  var lastRender = 0;
  var resumeAfterSeek = false;

  function emptyRow() {
    var row = new Array(COLS);
    for (var i = 0; i < COLS; i++) row[i] = { ch: ' ', fg: null, bold: false };
    return row;
  }

  function resetBuffer() {
    cells = new Array(ROWS);
    for (var y = 0; y < ROWS; y++) cells[y] = emptyRow();
    cx = 0;
    cy = 0;
    fg = null;
    bold = false;
    idx = 0;
  }

  function newline() {
    cx = 0;
    cy++;
    if (cy >= ROWS) {
      cells.shift();
      cells.push(emptyRow());
      cy = ROWS - 1;
    }
  }

  function writeChar(ch) {
    if (cx >= COLS) newline();
    if (cy < 0) cy = 0;
    if (cy >= ROWS) newline();
    cells[cy][cx] = { ch: ch, fg: fg, bold: bold };
    cx++;
  }

  function clearScreen() {
    for (var y = 0; y < ROWS; y++) cells[y] = emptyRow();
    cx = 0;
    cy = 0;
  }

  function eraseLine(mode) {
    if (mode === 1) {
      for (var x = 0; x <= Math.min(cx, COLS - 1); x++) cells[cy][x] = { ch: ' ', fg: null, bold: false };
    } else {
      for (var x2 = Math.max(cx, 0); x2 < COLS; x2++) cells[cy][x2] = { ch: ' ', fg: null, bold: false };
    }
  }

  function applySgr(body) {
    var parts = (body === '' ? ['0'] : body.split(';'));
    for (var i = 0; i < parts.length; i++) {
      var n = parseInt(parts[i] || '0', 10);
      if (n === 0) { fg = null; bold = false; }
      else if (n === 1) { bold = true; }
      else if (n === 22) { bold = false; }
      else if (n === 39) { fg = null; }
      else if (COLORS[n]) { fg = COLORS[n]; }
    }
  }

  function feed(data) {
    for (var i = 0; i < data.length; i++) {
      var ch = data.charAt(i);
      if (ch === '\x1b') {
        if (data.charAt(i + 1) === '[') {
          var j = i + 2;
          while (j < data.length && !/[A-Za-z]/.test(data.charAt(j))) j++;
          if (j >= data.length) break;
          var body = data.slice(i + 2, j);
          var final = data.charAt(j);
          if (final === 'm') applySgr(body);
          else if (final === 'J') {
            var mode = parseInt(body || '0', 10);
            if (mode === 2 || mode === 3) clearScreen();
          } else if (final === 'H') {
            cx = 0; cy = 0;
          } else if (final === 'K') {
            eraseLine(parseInt(body || '0', 10));
          }
          i = j;
          continue;
        }
        continue;
      }
      if (ch === '\r') { cx = 0; continue; }
      if (ch === '\n') { newline(); continue; }
      if (ch === '\b') { if (cx > 0) cx--; continue; }
      if (ch === '\t') {
        var spaces = 8 - (cx % 8);
        for (var s = 0; s < spaces; s++) writeChar(' ');
        continue;
      }
      if (ch < ' ') continue;
      writeChar(ch);
    }
  }

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function render() {
    var html = '';
    for (var y = 0; y < ROWS; y++) {
      var row = cells[y];
      var line = '';
      var run = '';
      var runStyle = '';
      for (var x = 0; x < COLS; x++) {
        var cell = row[x];
        var styleParts = [];
        if (cell.fg) styleParts.push('color:' + cell.fg);
        if (cell.bold) styleParts.push('font-weight:700');
        var style = styleParts.join(';');
        if (style !== runStyle) {
          if (run) {
            line += runStyle ? '<span style="' + runStyle + '">' + escapeHtml(run) + '</span>' : escapeHtml(run);
          }
          run = '';
          runStyle = style;
        }
        run += cell.ch;
      }
      if (run) {
        line += runStyle ? '<span style="' + runStyle + '">' + escapeHtml(run) + '</span>' : escapeHtml(run);
      }
      html += '<div class="cast-row">' + (line || ' ') + '</div>';
    }
    screenEl.innerHTML = html;
    if (screenEl.scrollHeight > screenEl.clientHeight + 8) {
      screenEl.scrollTop = screenEl.scrollHeight;
    }
  }

  function applyUpTo(t) {
    while (idx < EVENTS.length && EVENTS[idx][0] <= t + 0.0001) {
      feed(EVENTS[idx][2]);
      idx++;
    }
  }

  function fmt(t) {
    t = Math.max(0, t);
    var m = Math.floor(t / 60);
    var s = Math.floor(t % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function updateUI() {
    var pct = DURATION ? Math.min(1, Math.max(0, elapsed / DURATION)) : 0;
    if (rangeEl) rangeEl.value = Math.round(pct * 1000);
    if (timeEl) timeEl.textContent = fmt(elapsed) + ' / ' + fmt(DURATION);
  }

  function showPoster() {
    if (poster) poster.hidden = false;
  }

  function hidePoster() {
    if (poster) poster.hidden = true;
  }

  function resetTo(t) {
    elapsed = Math.min(DURATION, Math.max(0, t));
    resetBuffer();
    applyUpTo(elapsed);
    render();
    updateUI();
  }

  function pause() {
    if (!playing) return;
    playing = false;
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    if (playBtn) {
      playBtn.textContent = '▶ Reproducir';
      playBtn.classList.add('cast-primary');
    }
  }

  function tick(now) {
    if (!playing) return;
    var t = playFrom + ((now - playStart) / 1000) * speed;
    if (t >= DURATION) {
      elapsed = DURATION;
      applyUpTo(DURATION);
      render();
      updateUI();
      pause();
      return;
    }
    elapsed = t;
    applyUpTo(t);
    if (now - lastRender >= 33) {
      render();
      lastRender = now;
    }
    updateUI();
    raf = requestAnimationFrame(tick);
  }

  function play() {
    if (playing) return;
    if (!started || elapsed >= DURATION - 0.02) {
      resetTo(0);
      started = true;
    }
    hidePoster();
    playing = true;
    playFrom = elapsed;
    playStart = performance.now();
    speed = parseFloat(speedEl ? speedEl.value : '1') || 1;
    if (playBtn) {
      playBtn.textContent = 'Pausar';
      playBtn.classList.remove('cast-primary');
    }
    raf = requestAnimationFrame(tick);
  }

  function togglePlay() {
    if (playing) pause(); else play();
  }

  function restart() {
    pause();
    resetTo(0);
    started = true;
    hidePoster();
    play();
  }

  function seekFromRange() {
    if (!rangeEl) return;
    var t = (parseFloat(rangeEl.value) / 1000) * DURATION;
    if (playing) {
      resumeAfterSeek = true;
      pause();
    }
    resetTo(t);
    started = true;
    hidePoster();
  }

  // Preview estático para el póster (sin alterar el tiempo de reproducción).
  resetBuffer();
  applyUpTo(Math.min(4.2, DURATION));
  render();
  elapsed = 0;
  updateUI();
  showPoster();

  if (playBtn) playBtn.addEventListener('click', togglePlay);
  if (startBtn) startBtn.addEventListener('click', play);
  if (restartBtn) restartBtn.addEventListener('click', restart);
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      pause();
      var text = (screenEl.innerText || screenEl.textContent || '').replace(/\u00a0/g, ' ').trim();
      var done = function (ok) {
        copyBtn.textContent = ok ? '✓ Copiado' : 'No se pudo copiar';
        setTimeout(function () { copyBtn.textContent = '⧉ Copiar comandos'; }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { fallback(); });
      } else {
        fallback();
      }
      function fallback() {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        var ok = false;
        try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
        document.body.removeChild(ta);
        done(ok);
      }
    });
  }
  if (rangeEl) {
    rangeEl.addEventListener('input', seekFromRange);
    rangeEl.addEventListener('change', function () {
      if (resumeAfterSeek) {
        resumeAfterSeek = false;
        play();
      }
    });
  }
  if (speedEl) {
    speedEl.addEventListener('change', function () {
      var newSpeed = parseFloat(this.value) || 1;
      if (playing) {
        playFrom = elapsed;
        playStart = performance.now();
      }
      speed = newSpeed;
    });
  }
  if (fullBtn) {
    fullBtn.addEventListener('click', function () {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else if (shell.requestFullscreen) {
        shell.requestFullscreen();
      }
    });
  }
  document.addEventListener('fullscreenchange', function () {
    if (fullBtn) fullBtn.textContent = document.fullscreenElement ? '⤢ Salir' : '⛶';
  });
  screenEl.tabIndex = 0;
  screenEl.addEventListener('keydown', function (e) {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      togglePlay();
    }
  });
})();
