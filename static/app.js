const fmt = (n) => '$' + Number(n || 0).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (res.status === 401) {
    window.location.href = '/login';
    return new Promise(() => {}); // corta la ejecución, ya estamos redirigiendo
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Ocurrió un error');
  return data;
}

let categoriaSeleccionada = null;
let deudaSeleccionada = null;
let graficoGastos = null;

const PALETA_GRAFICO = ['#AEE62B', '#0E2A1D', '#FF5A44', '#3E8ED0', '#F2B705', '#8E5AE2', '#2AA876', '#C97B3E'];

function mostrarAlerta(id, mensaje) {
  const el = document.getElementById(id);
  el.textContent = mensaje || '';
  if (mensaje) setTimeout(() => { if (el.textContent === mensaje) el.textContent = ''; }, 5000);
}

function actualizarReloj() {
  const el = document.getElementById('fecha-hora');
  if (!el) return;
  const ahora = new Date();
  const fecha = ahora.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const hora = ahora.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  el.textContent = `${fecha.charAt(0).toUpperCase()}${fecha.slice(1)} · ${hora}`;
}

async function cargarConfig() {
  const cfg = await api('/api/config');
  document.getElementById('in-sueldo').value = cfg.sueldo || '';
  document.getElementById('in-gastos').value = cfg.monto_gastos || '';
  document.getElementById('in-ahorro').value = cfg.monto_ahorro || '';
  return cfg;
}

async function cargarOverview() {
  const resumen = await api('/api/resumen');
  const gastosBarra = document.getElementById('barra-gastos');
  const ahorroBarra = document.getElementById('barra-ahorro');
  const pctGastos = resumen.total_asignado > 0 ? Math.min(100, (resumen.total_gastado / resumen.total_asignado) * 100) : 0;
  const pctAhorro = resumen.ahorro.meta > 0 ? Math.min(100, (resumen.ahorro.ahorrado / resumen.ahorro.meta) * 100) : 0;
  gastosBarra.style.width = pctGastos + '%';
  gastosBarra.classList.toggle('limite', pctGastos >= 100);
  ahorroBarra.style.width = pctAhorro + '%';
  document.getElementById('txt-gastos').textContent = `${fmt(resumen.total_gastado)} / ${fmt(resumen.config.monto_gastos)}`;
  document.getElementById('txt-ahorro').textContent = `${fmt(resumen.ahorro.ahorrado)} / ${fmt(resumen.ahorro.meta)}`;
  dibujarGrafico(resumen.detalle);
  return resumen;
}

function dibujarGrafico(detalle) {
  const canvas = document.getElementById('grafico-gastos');
  const vacio = document.getElementById('grafico-vacio');
  if (!canvas || typeof Chart === 'undefined') return;
  const conGasto = (detalle || []).filter(d => d.gastado > 0);
  if (!conGasto.length) {
    canvas.style.display = 'none';
    vacio.style.display = '';
    if (graficoGastos) { graficoGastos.destroy(); graficoGastos = null; }
    return;
  }
  canvas.style.display = '';
  vacio.style.display = 'none';
  const labels = conGasto.map(d => d.nombre);
  const valores = conGasto.map(d => d.gastado);
  const colores = conGasto.map((_, i) => PALETA_GRAFICO[i % PALETA_GRAFICO.length]);
  if (graficoGastos) {
    graficoGastos.data.labels = labels;
    graficoGastos.data.datasets[0].data = valores;
    graficoGastos.data.datasets[0].backgroundColor = colores;
    graficoGastos.update();
    return;
  }
  graficoGastos = new Chart(canvas, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: valores, backgroundColor: colores, borderWidth: 0 }] },
    options: {
      plugins: {
        legend: { position: 'bottom', labels: { color: '#0E2A1D', font: { family: 'Inter' } } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${fmt(ctx.parsed)}` } },
      },
    },
  });
}

function tarjetaCategoria(cat) {
  const div = document.createElement('div');
  const agotada = cat.disponible <= 0;
  div.className = 'categoria' + (agotada ? ' agotada' : '');
  const pct = cat.monto_asignado > 0 ? Math.min(100, (cat.gastado / cat.monto_asignado) * 100) : 0;
  div.innerHTML = `
    <div class="categoria__cabecera">
      <span class="categoria__titulo">
        <span class="categoria__nombre">${cat.nombre}</span>
        <span class="categoria__badge categoria__badge--${cat.tipo}">${cat.tipo === 'activo' ? 'Activo' : 'Pasivo'}</span>
      </span>
      <span class="categoria__montos">${fmt(cat.gastado)} / ${fmt(cat.monto_asignado)}</span>
    </div>
    <div class="barra"><div class="barra__fill barra__fill--gastos" style="width:${pct}%"></div></div>
    <div class="categoria__acciones">
      <button class="btn agregar-gasto" ${agotada ? 'disabled' : ''}>${agotada ? 'Límite alcanzado' : 'Agregar gasto'}</button>
      <button class="btn eliminar-cat">Eliminar</button>
    </div>
  `;
  div.querySelector('.agregar-gasto').addEventListener('click', () => abrirModalGasto(cat));
  div.querySelector('.eliminar-cat').addEventListener('click', async () => {
    if (!confirm(`¿Eliminar "${cat.nombre}"? Se borra la categoría, no el registro de gastos ya hechos.`)) return;
    await api(`/api/categorias/${cat.id}`, { method: 'DELETE' });
    refrescarTodo();
  });
  return div;
}

async function cargarCategorias() {
  const cats = await api('/api/categorias');
  const contActivos = document.getElementById('cont-activos');
  const contPasivos = document.getElementById('cont-pasivos');
  contActivos.innerHTML = '';
  contPasivos.innerHTML = '';
  const activos = cats.filter(c => c.tipo === 'activo');
  const pasivos = cats.filter(c => c.tipo === 'pasivo');
  document.getElementById('lista-activos').style.display = activos.length ? '' : 'none';
  document.getElementById('lista-pasivos').style.display = pasivos.length ? '' : 'none';
  activos.forEach(c => contActivos.appendChild(tarjetaCategoria(c)));
  pasivos.forEach(c => contPasivos.appendChild(tarjetaCategoria(c)));
}

async function cargarAhorros() {
  const data = await api('/api/ahorros');
  const ul = document.getElementById('lista-ahorros');
  ul.innerHTML = '';
  data.items.slice(0, 8).forEach(item => {
    const li = document.createElement('li');
    const fecha = new Date(item.fecha).toLocaleDateString('es-AR');
    li.innerHTML = `<span>${item.descripcion || 'Ahorro'} · ${fecha}</span><span>${fmt(item.monto)}</span>`;
    ul.appendChild(li);
  });
}

async function cargarIngresos() {
  const data = await api('/api/ingresos');
  document.getElementById('txt-ingresos-total').textContent = `Total del mes: ${fmt(data.total)}`;
  const ul = document.getElementById('lista-ingresos');
  ul.innerHTML = '';
  data.items.slice(0, 8).forEach(item => {
    const li = document.createElement('li');
    const fecha = new Date(item.fecha).toLocaleDateString('es-AR');
    li.innerHTML = `<span>${item.descripcion || 'Ingreso'} · ${fecha}</span><span>${fmt(item.monto)}</span>`;
    ul.appendChild(li);
  });
}

function tarjetaDeuda(deuda) {
  const div = document.createElement('div');
  div.className = 'deuda' + (deuda.saldada ? ' saldada' : deuda.vencida ? ' vencida' : '');
  const pct = deuda.monto_total > 0 ? Math.min(100, (deuda.monto_pagado / deuda.monto_total) * 100) : 0;
  const venceTxt = deuda.fecha_vencimiento
    ? new Date(deuda.fecha_vencimiento + 'T00:00:00').toLocaleDateString('es-AR')
    : 'Sin fecha';
  let etiqueta = `Vence ${venceTxt}`;
  if (deuda.saldada) etiqueta = 'Saldada';
  else if (deuda.vencida) etiqueta = `Vencida desde ${venceTxt}`;
  div.innerHTML = `
    <div class="categoria__cabecera">
      <span class="categoria__titulo">
        <span class="categoria__nombre">${deuda.nombre}</span>
        <span class="deuda__etiqueta">${etiqueta}</span>
      </span>
      <span class="categoria__montos">${fmt(deuda.monto_pagado)} / ${fmt(deuda.monto_total)}</span>
    </div>
    <div class="barra"><div class="barra__fill barra__fill--gastos" style="width:${pct}%"></div></div>
    <div class="categoria__acciones">
      <button class="btn pagar-deuda" ${deuda.saldada ? 'disabled' : ''}>${deuda.saldada ? 'Saldada' : 'Registrar pago'}</button>
      <button class="btn eliminar-deuda">Eliminar</button>
    </div>
  `;
  div.querySelector('.pagar-deuda').addEventListener('click', () => abrirModalPago(deuda));
  div.querySelector('.eliminar-deuda').addEventListener('click', async () => {
    if (!confirm(`¿Eliminar la deuda "${deuda.nombre}"?`)) return;
    await api(`/api/deudas/${deuda.id}`, { method: 'DELETE' });
    refrescarTodo();
  });
  return div;
}

async function cargarDeudas() {
  const deudas = await api('/api/deudas');
  const cont = document.getElementById('cont-deudas');
  cont.innerHTML = '';
  if (!deudas.length) {
    cont.innerHTML = '<p class="hint">No tenés deudas cargadas.</p>';
  } else {
    deudas.forEach(d => cont.appendChild(tarjetaDeuda(d)));
  }
  const vencidas = deudas.filter(d => d.vencida);
  const banner = document.getElementById('alerta-deudas');
  if (vencidas.length) {
    banner.style.display = '';
    const items = vencidas.map(d => `${d.nombre} (${fmt(d.pendiente)})`).join(', ');
    banner.innerHTML = `⚠️ Tenés ${vencidas.length} deuda${vencidas.length > 1 ? 's' : ''} vencida${vencidas.length > 1 ? 's' : ''} sin saldar: ${items}`;
  } else {
    banner.style.display = 'none';
  }
}

async function cargarResumen() {
  const resumen = await api('/api/resumen');
  const cont = document.getElementById('resumen-contenido');
  const filas = (titulo, asignado, gastado) => `
    <div class="resumen__grupo-titulo">${titulo}</div>
    <div class="resumen__fila"><span>Asignado</span><span>${fmt(asignado)}</span></div>
    <div class="resumen__fila"><span>Gastado</span><span>${fmt(gastado)}</span></div>
    <div class="resumen__fila"><span>Disponible</span><span>${fmt(asignado - gastado)}</span></div>
  `;
  cont.innerHTML = `
    <div class="resumen__grupo-titulo">Ingresos</div>
    <div class="resumen__fila"><span>Registrados este mes</span><span>${fmt(resumen.ingresos_total)}</span></div>
    ${filas('Activos', resumen.activos.asignado, resumen.activos.gastado)}
    ${filas('Pasivos', resumen.pasivos.asignado, resumen.pasivos.gastado)}
    <div class="resumen__grupo-titulo">Ahorro</div>
    <div class="resumen__fila"><span>Meta</span><span>${fmt(resumen.ahorro.meta)}</span></div>
    <div class="resumen__fila"><span>Ahorrado</span><span>${fmt(resumen.ahorro.ahorrado)}</span></div>
    <div class="resumen__fila resumen__fila--total"><span>Total gastado del mes</span><span>${fmt(resumen.total_gastado)}</span></div>
  `;
}

function resumenHistoricoHTML(r) {
  return `
    <div class="resumen__fila"><span>Ingresos</span><span>${fmt(r.ingresos_total || 0)}</span></div>
    <div class="resumen__fila"><span>Activos gastado</span><span>${fmt(r.activos.gastado)} / ${fmt(r.activos.asignado)}</span></div>
    <div class="resumen__fila"><span>Pasivos gastado</span><span>${fmt(r.pasivos.gastado)} / ${fmt(r.pasivos.asignado)}</span></div>
    <div class="resumen__fila"><span>Ahorrado</span><span>${fmt(r.ahorro.ahorrado)} / ${fmt(r.ahorro.meta)}</span></div>
    <div class="resumen__fila resumen__fila--total"><span>Total gastado</span><span>${fmt(r.total_gastado)}</span></div>
  `;
}

async function cargarHistorial() {
  const cierres = await api('/api/historial');
  const cont = document.getElementById('historial-contenido');
  if (!cierres.length) {
    cont.innerHTML = '<p class="hint">Todavía no cerraste ningún mes.</p>';
    return;
  }
  cont.innerHTML = cierres.map(c => `
    <details class="historial__mes">
      <summary>${c.mes} · cerrado el ${new Date(c.fecha_cierre).toLocaleDateString('es-AR')}</summary>
      ${resumenHistoricoHTML(c.resumen)}
    </details>
  `).join('');
}

function abrirModalGasto(cat) {
  categoriaSeleccionada = cat;
  document.getElementById('modal-gasto-titulo').textContent = `Gasto en "${cat.nombre}"`;
  document.getElementById('gasto-monto').value = '';
  document.getElementById('gasto-desc').value = '';
  document.getElementById('gasto-alerta').textContent = '';
  document.getElementById('modal-gasto').classList.add('activo');
}

function cerrarModalGasto() {
  categoriaSeleccionada = null;
  document.getElementById('modal-gasto').classList.remove('activo');
}

function abrirModalPago(deuda) {
  deudaSeleccionada = deuda;
  document.getElementById('modal-pago-titulo').textContent = `Pago de "${deuda.nombre}" (pendiente: ${fmt(deuda.pendiente)})`;
  document.getElementById('pago-monto').value = '';
  document.getElementById('pago-alerta').textContent = '';
  document.getElementById('modal-pago').classList.add('activo');
}

function cerrarModalPago() {
  deudaSeleccionada = null;
  document.getElementById('modal-pago').classList.remove('activo');
}

async function refrescarTodo() {
  await Promise.all([cargarCategorias(), cargarOverview(), cargarResumen(), cargarAhorros(), cargarIngresos(), cargarDeudas()]);
}

document.getElementById('form-config').addEventListener('submit', async (e) => {
  e.preventDefault();
  const sueldo = document.getElementById('in-sueldo').value;
  const monto_gastos = document.getElementById('in-gastos').value;
  const monto_ahorro = document.getElementById('in-ahorro').value;
  try {
    await api('/api/config', { method: 'POST', body: JSON.stringify({ sueldo, monto_gastos, monto_ahorro }) });
    mostrarAlerta('config-alerta', '');
    refrescarTodo();
  } catch (err) {
    mostrarAlerta('config-alerta', err.message);
  }
});

document.getElementById('form-categoria').addEventListener('submit', async (e) => {
  e.preventDefault();
  const nombre = document.getElementById('cat-nombre').value;
  const tipo = document.getElementById('cat-tipo').value;
  const monto_asignado = document.getElementById('cat-monto').value;
  try {
    await api('/api/categorias', { method: 'POST', body: JSON.stringify({ nombre, tipo, monto_asignado }) });
    document.getElementById('form-categoria').reset();
    mostrarAlerta('categoria-alerta', '');
    refrescarTodo();
  } catch (err) {
    mostrarAlerta('categoria-alerta', err.message);
  }
});

document.getElementById('form-ahorro').addEventListener('submit', async (e) => {
  e.preventDefault();
  const monto = document.getElementById('ahorro-monto').value;
  const descripcion = document.getElementById('ahorro-desc').value;
  try {
    await api('/api/ahorros', { method: 'POST', body: JSON.stringify({ monto, descripcion }) });
    document.getElementById('form-ahorro').reset();
    mostrarAlerta('ahorro-alerta', '');
    refrescarTodo();
  } catch (err) {
    mostrarAlerta('ahorro-alerta', err.message);
  }
});

document.getElementById('form-ingreso').addEventListener('submit', async (e) => {
  e.preventDefault();
  const monto = document.getElementById('ingreso-monto').value;
  const descripcion = document.getElementById('ingreso-desc').value;
  try {
    await api('/api/ingresos', { method: 'POST', body: JSON.stringify({ monto, descripcion }) });
    document.getElementById('form-ingreso').reset();
    mostrarAlerta('ingreso-alerta', '');
    refrescarTodo();
  } catch (err) {
    mostrarAlerta('ingreso-alerta', err.message);
  }
});

document.getElementById('form-deuda').addEventListener('submit', async (e) => {
  e.preventDefault();
  const nombre = document.getElementById('deuda-nombre').value;
  const monto_total = document.getElementById('deuda-monto').value;
  const fecha_vencimiento = document.getElementById('deuda-vencimiento').value;
  try {
    await api('/api/deudas', { method: 'POST', body: JSON.stringify({ nombre, monto_total, fecha_vencimiento }) });
    document.getElementById('form-deuda').reset();
    mostrarAlerta('deuda-alerta', '');
    refrescarTodo();
  } catch (err) {
    mostrarAlerta('deuda-alerta', err.message);
  }
});

document.getElementById('gasto-confirmar').addEventListener('click', async () => {
  if (!categoriaSeleccionada) return;
  const monto = document.getElementById('gasto-monto').value;
  const descripcion = document.getElementById('gasto-desc').value;
  try {
    await api('/api/gastos', { method: 'POST', body: JSON.stringify({ categoria_id: categoriaSeleccionada.id, monto, descripcion }) });
    cerrarModalGasto();
    refrescarTodo();
  } catch (err) {
    document.getElementById('gasto-alerta').textContent = err.message;
  }
});

document.getElementById('gasto-cancelar').addEventListener('click', cerrarModalGasto);

document.getElementById('pago-confirmar').addEventListener('click', async () => {
  if (!deudaSeleccionada) return;
  const monto = document.getElementById('pago-monto').value;
  try {
    await api(`/api/deudas/${deudaSeleccionada.id}/pago`, { method: 'POST', body: JSON.stringify({ monto }) });
    cerrarModalPago();
    refrescarTodo();
  } catch (err) {
    document.getElementById('pago-alerta').textContent = err.message;
  }
});

document.getElementById('pago-cancelar').addEventListener('click', cerrarModalPago);

document.getElementById('btn-cerrar-mes').addEventListener('click', async () => {
  if (!confirm('Esto archiva el mes actual en el historial y reinicia gastos, ahorros e ingresos registrados (las deudas no se borran). ¿Continuar?')) return;
  await api('/api/cerrar_mes', { method: 'POST', body: JSON.stringify({}) });
  await Promise.all([refrescarTodo(), cargarHistorial()]);
});

(async function init() {
  actualizarReloj();
  setInterval(actualizarReloj, 30000);
  await cargarConfig();
  await refrescarTodo();
  await cargarHistorial();
})();
