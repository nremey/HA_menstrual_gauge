class MenstruationGaugeCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: 'custom:menstruation-gauge-card',
      entity: 'sensor.menstruation_gauge',
      period_duration_days: 5,
      title: 'Cycle Gauge'
    };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error('entity is required');
    }
    this._config = {
      show_editor: true,
      ...config
    };
    this._viewDate = new Date();
    this._editorOpen = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _ensureRoot() {
    if (this.shadowRoot) return;
    this.attachShadow({ mode: 'open' });
  }

  _normalizeISO(value) {
    const m = String(value || '').trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    return `${m[1]}-${m[2]}-${m[3]}`;
  }

  _parseISO(iso) {
    const n = this._normalizeISO(iso);
    if (!n) return null;
    const [y, m, d] = n.split('-').map((x) => Number(x));
    const dt = new Date(y, m - 1, d, 12, 0, 0, 0);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }

  _isoFromDate(dt) {
    if (!(dt instanceof Date) || Number.isNaN(dt.getTime())) return '';
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, '0');
    const d = String(dt.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  _dayDiff(aIso, bIso) {
    const a = this._parseISO(aIso);
    const b = this._parseISO(bIso);
    if (!a || !b) return 0;
    return Math.round((a.getTime() - b.getTime()) / 86400000);
  }

  _monthDays(dt) {
    return new Date(dt.getFullYear(), dt.getMonth() + 1, 0).getDate();
  }

  _buildModel() {
    const stateObj = this._hass?.states?.[this._config.entity];
    const attrs = stateObj?.attributes || {};
    const history = Array.isArray(attrs.history) ? attrs.history.map((x) => this._normalizeISO(x)).filter(Boolean) : [];
    const confirmedSet = new Set(history);
    const periodDuration = Math.max(1, Math.min(14, Number(this._config.period_duration_days || attrs.period_duration_days || 5)));
    const predicted = this._normalizeISO(attrs.next_predicted_start);
    const fertileStart = this._normalizeISO(attrs.fertile_window_start);
    const fertileEnd = this._normalizeISO(attrs.fertile_window_end);

    const viewDate = this._viewDate || new Date();
    const daysInMonth = this._monthDays(viewDate);
    const series = [];
    for (let day = 1; day <= daysInMonth; day++) {
      const dt = new Date(viewDate.getFullYear(), viewDate.getMonth(), day, 12, 0, 0, 0);
      const iso = this._isoFromDate(dt);
      series.push({
        day,
        iso,
        confirmed: confirmedSet.has(iso),
        fertile: fertileStart && fertileEnd ? (this._dayDiff(iso, fertileStart) >= 0 && this._dayDiff(fertileEnd, iso) >= 0) : false
      });
    }

    return {
      stateObj,
      state: String(stateObj?.state || 'neutral'),
      history,
      confirmedSet,
      predicted,
      periodDuration,
      fertileStart,
      fertileEnd,
      daysInMonth,
      series,
      todayIso: this._isoFromDate(new Date())
    };
  }

  _stateBg(state) {
    if (state === 'period') return 'linear-gradient(135deg, rgba(252,231,243,.97), rgba(255,241,246,.95))';
    if (state === 'fertile') return 'linear-gradient(135deg, rgba(254,252,232,.97), rgba(255,255,255,.95))';
    if (state === 'pms') return 'linear-gradient(135deg, rgba(255,241,246,.96), rgba(255,250,252,.94))';
    return 'linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,255,255,.95))';
  }

  _polar(cx, cy, r, deg) {
    const a = deg * Math.PI / 180;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  }

  _arcPath(cx, cy, r, startDeg, endDeg) {
    const s = this._polar(cx, cy, r, startDeg);
    const e = this._polar(cx, cy, r, endDeg);
    const span = ((endDeg - startDeg) % 360 + 360) % 360;
    const largeArc = span > 180 ? 1 : 0;
    return `M ${s.x.toFixed(1)} ${s.y.toFixed(1)} A ${r.toFixed(1)} ${r.toFixed(1)} 0 ${largeArc} 1 ${e.x.toFixed(1)} ${e.y.toFixed(1)}`;
  }

  _renderGauge(model) {
    const cx = 210;
    const cy = 210;
    const rInner = 126;
    const baseTick = 4.2;
    const extraBar = 26;
    const total = model.daysInMonth || 30;
    const gaugeWidth = Number(this._lastCardWidth || 0);
    let labelStep = 1;
    if (gaugeWidth > 0 && gaugeWidth < 320) labelStep = 5;
    else if (gaugeWidth > 0 && gaugeWidth < 380) labelStep = 3;
    else if (gaugeWidth > 0 && gaugeWidth < 480) labelStep = 2;
    const now = new Date();
    const dayNow = now.getDate();
    const handAngle = -90 + ((((dayNow - 1) + now.getHours() / 24) / total) * 360);

    const baseTicks = model.series.map((_, i) => {
      const angle = -90 + ((i / total) * 360);
      return `<g transform="translate(${cx} ${cy}) rotate(${angle})"><rect x="-1.3" y="-${(rInner + baseTick).toFixed(1)}" width="2.6" height="${baseTick.toFixed(1)}" rx="1.2" fill="rgba(190,24,93,.22)"></rect></g>`;
    }).join('');

    const dayLabels = model.series.map((step, i) => {
      const isFirst = step.day === 1;
      const isLast = step.day === total;
      if (!isFirst && !isLast && (step.day % labelStep !== 0)) return '';
      const angle = -90 + ((i / total) * 360);
      const pos = this._polar(cx, cy, 178, angle);
      return `<text x="${pos.x.toFixed(1)}" y="${pos.y.toFixed(1)}" fill="rgba(131,24,67,.68)" font-size="10" text-anchor="middle" dominant-baseline="middle">${step.day}</text>`;
    }).join('');

    const confirmedBars = model.series.map((step, i) => {
      if (!step.confirmed) return '';
      const angle = -90 + ((i / total) * 360);
      const len = extraBar;
      return `<g transform="translate(${cx} ${cy}) rotate(${angle})"><rect x="-2.1" y="-${(rInner + baseTick + len).toFixed(1)}" width="4.2" height="${len.toFixed(1)}" rx="1.8" fill="#be123c" fill-opacity="0.78"></rect></g>`;
    }).join('');

    const fertileBars = model.series.map((step) => {
      if (!step.fertile) return '';
      const day = step.day;
      const startAngle = -90 + ((((day - 1) + 0.08) / total) * 360);
      const endAngle = -90 + ((((day - 0.08) / total) * 360));
      const dPath = this._arcPath(cx, cy, rInner + extraBar * 0.46, startAngle, endAngle);
      return `<path d="${dPath}" fill="none" stroke="#facc15" stroke-width="6" stroke-linecap="round" stroke-opacity=".62"></path>`;
    }).join('');

    let predictedMarker = '';
    let predictedBars = '';
    const predictedDt = this._parseISO(model.predicted);
    const inView = predictedDt
      && predictedDt.getFullYear() === this._viewDate.getFullYear()
      && predictedDt.getMonth() === this._viewDate.getMonth();
    if (inView) {
      const pDay = predictedDt.getDate();
      const marker = (offset, fill, radius) => {
        const d = pDay + offset;
        if (d < 1 || d > total) return '';
        const angle = -90 + ((((d - 1) + 0.5) / total) * 360);
        const pos = this._polar(cx, cy, rInner + extraBar + 3, angle);
        return `<circle cx="${pos.x.toFixed(1)}" cy="${pos.y.toFixed(1)}" r="${radius}" fill="${fill}" stroke="#ffe4e6" stroke-width="2"></circle>`;
      };
      predictedMarker = `${marker(-1, '#fb7185', '4.6')}${marker(0, '#be123c', '5.5')}${marker(1, '#fb7185', '4.6')}`;

      predictedBars = Array.from({ length: model.periodDuration }).map((_, idx) => {
        const dt = new Date(predictedDt);
        dt.setDate(dt.getDate() + idx);
        if (dt.getMonth() !== this._viewDate.getMonth() || dt.getFullYear() !== this._viewDate.getFullYear()) return '';
        const day = dt.getDate();
        const startAngle = -90 + ((((day - 1) + 0.06) / total) * 360);
        const endAngle = -90 + ((((day - 0.06) / total) * 360));
        const dPath = this._arcPath(cx, cy, rInner + extraBar * 0.74, startAngle, endAngle);
        const alpha = idx === 0 ? 0.60 : 0.38;
        const sw = idx === 0 ? 8.6 : 7.2;
        return `<path d="${dPath}" fill="none" stroke="#be123c" stroke-width="${sw}" stroke-linecap="round" stroke-opacity="${alpha}"></path>`;
      }).join('');
    }

    const handA = this._polar(cx, cy, rInner - 2, handAngle);
    const handB = this._polar(cx, cy, rInner + extraBar - 2, handAngle);
    const monthLabel = new Intl.DateTimeFormat(this._hass?.locale?.language || 'de', { month: 'long' }).format(this._viewDate);

    return `
      <svg class="gauge" viewBox="0 0 420 420" role="img" aria-label="Menstruation gauge">
        <text x="${cx}" y="44" class="month">${monthLabel}</text>
        ${dayLabels}
        ${baseTicks}
        ${fertileBars}
        ${predictedBars}
        ${confirmedBars}
        ${predictedMarker}
        <line x1="${handA.x.toFixed(1)}" y1="${handA.y.toFixed(1)}" x2="${handB.x.toFixed(1)}" y2="${handB.y.toFixed(1)}" stroke="#be123c" stroke-width="1.9" stroke-linecap="round"></line>
        <circle cx="${cx}" cy="${cy}" r="106" fill="none" stroke="rgba(190,24,93,.16)" stroke-width="1"></circle>
      </svg>
    `;
  }

  _calendarGrid(model) {
    const y = this._viewDate.getFullYear();
    const m = this._viewDate.getMonth();
    const first = new Date(y, m, 1, 12, 0, 0, 0);
    const count = new Date(y, m + 1, 0).getDate();
    const firstDowMon0 = (first.getDay() + 6) % 7;
    const totalCells = Math.ceil((firstDowMon0 + count) / 7) * 7;
    const dows = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

    const items = [];
    dows.forEach((d) => items.push(`<div class="dow">${d}</div>`));

    for (let i = 0; i < totalCells; i++) {
      const day = i - firstDowMon0 + 1;
      const valid = day >= 1 && day <= count;
      if (!valid) {
        items.push('<button class="day other" disabled></button>');
        continue;
      }
      const iso = this._isoFromDate(new Date(y, m, day, 12, 0, 0, 0));
      const active = model.confirmedSet.has(iso);
      const today = iso === model.todayIso;
      items.push(`<button class="day ${active ? 'active' : ''} ${today ? 'today' : ''}" data-iso="${iso}">${day}</button>`);
    }
    return items.join('');
  }

  async _toggleCycleStart(iso) {
    const model = this._buildModel();
    const service = model.confirmedSet.has(iso) ? 'remove_cycle_start' : 'add_cycle_start';
    await this._hass.callService('menstruation_gauge', service, { date: iso });
  }

  _attachHandlers() {
    this.shadowRoot.querySelector('[data-nav="prev"]')?.addEventListener('click', () => {
      this._viewDate = new Date(this._viewDate.getFullYear(), this._viewDate.getMonth() - 1, 1);
      this._render();
    });
    this.shadowRoot.querySelector('[data-nav="next"]')?.addEventListener('click', () => {
      this._viewDate = new Date(this._viewDate.getFullYear(), this._viewDate.getMonth() + 1, 1);
      this._render();
    });
    this.shadowRoot.querySelector('[data-action="toggle-editor"]')?.addEventListener('click', () => {
      this._editorOpen = !this._editorOpen;
      this._render();
    });

    this.shadowRoot.querySelectorAll('.day[data-iso]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const iso = btn.getAttribute('data-iso');
        if (!iso) return;
        await this._toggleCycleStart(iso);
      });
    });
  }

  _render() {
    this._ensureRoot();
    if (!this._config || !this._hass) return;

    const model = this._buildModel();
    this._lastCardWidth = this.getBoundingClientRect()?.width || 0;
    const locale = this._hass?.locale?.language || 'de';
    const monthYear = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(this._viewDate);
    const countdown = Number.isFinite(model.stateObj?.attributes?.days_until_next_start)
      ? `${model.stateObj.attributes.days_until_next_start} ${locale.startsWith('de') ? 'Tage' : 'days'}`
      : (locale.startsWith('de') ? '-- Tage' : '-- days');

    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          border-radius: 16px;
          border: 1px solid rgba(190,24,93,.20);
          background: ${this._stateBg(model.state)};
          color: #4a044e;
          box-shadow: 0 8px 20px rgba(131,24,67,.10);
          padding: 10px;
          overflow: hidden;
        }
        .wrap { display: grid; gap: 10px; }
        .gauge-wrap { position: relative; max-width: 420px; width: 100%; aspect-ratio: 1/1; margin: 0 auto; }
        .gauge { width: 100%; height: 100%; display: block; }
        .month { font-size: 12px; fill: rgba(131,24,67,.72); font-weight: 700; letter-spacing: .02em; text-anchor: middle; dominant-baseline: middle; }
        .center { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; }
        .countdown { pointer-events: auto; border-radius: 999px; border: 1px solid rgba(190,24,93,.18); padding: 4px 10px; background: rgba(255,255,255,.44); cursor: pointer; font-size: 1.05rem; font-weight: 700; color: #831843; }
        .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .title { font-weight: 700; }
        .nav { display: inline-flex; gap: 6px; }
        .btn { border: 1px solid rgba(190,24,93,.25); border-radius: 8px; background: #fff; color: #831843; padding: 4px 8px; cursor: pointer; }
        .editor { display: ${this._editorOpen ? 'grid' : 'none'}; gap: 8px; }
        .grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
        .dow { text-align: center; font-size: 12px; opacity: .75; }
        .day { min-height: 32px; border: 1px solid rgba(190,24,93,.16); border-radius: 8px; background: #fff; color: #6b1b4a; cursor: pointer; }
        .day.active { background: #be123c; color: #fff; border-color: #be123c; }
        .day.today { outline: 2px solid rgba(190,24,93,.35); }
        .day.other { opacity: .3; }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="gauge-wrap">
            ${this._renderGauge(model)}
            <div class="center"><button class="countdown" data-action="toggle-editor">${countdown}</button></div>
          </div>
          ${this._config.show_editor ? `
          <div class="editor">
            <div class="toolbar">
              <div class="title">${monthYear}</div>
              <div class="nav">
                <button class="btn" data-nav="prev">◀</button>
                <button class="btn" data-nav="next">▶</button>
              </div>
            </div>
            <div class="grid">${this._calendarGrid(model)}</div>
          </div>` : ''}
        </div>
      </ha-card>
    `;

    this._attachHandlers();
  }
}

customElements.define('menstruation-gauge-card', MenstruationGaugeCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'menstruation-gauge-card',
  name: 'Menstruation Gauge Card',
  description: 'Cycle gauge with click-to-edit cycle start history.'
});
