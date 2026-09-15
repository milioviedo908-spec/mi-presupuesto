const fmt = (n) => '$' + Number(n || 0).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Ocurrió un error');
  return data;
}

let categoriaSeleccionada = null;

function mostrarAlerta(id, mensaje) {
  const el = document.getElementById(id);
  el.textContent = mensaje || '';
  if (mensaje) setTimeout(() => { if (el.textContent === mensaje) el.textContent = ''; }, 5000);
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
  return resumen;
}

function tarjetaCategoria(cat) {
  const div = document.createElement('div');
  const agotada = cat.disponible <= 0;
  div.className = 'categoria' + (agotada ? ' agotada' : '');
  const pct = cat.monto_asignado > 0 ? Math.min(100, (cat.gastado / cat.monto_asignado) * 100) : 0;
  div.innerHTML = `
    <div class="categoria__cabecera">
      <span class="categoria__nombre">${cat.nombre}</span>
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

async function refrescarTodo() {
  await Promise.all([cargarCategorias(), cargarOverview(), cargarResumen(), cargarAhorros()]);
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

document.getElementById('btn-cerrar-mes').addEventListener('click', async () => {
  if (!confirm('Esto archiva el mes actual en el historial y reinicia los gastos y ahorros registrados. ¿Continuar?')) return;
  await api('/api/cerrar_mes', { method: 'POST', body: JSON.stringify({}) });
  await Promise.all([refrescarTodo(), cargarHistorial()]);
});

(async function init() {
  document.getElementById('mes-actual').textContent = new Date().toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });
  await cargarConfig();
  await refrescarTodo();
  await cargarHistorial();
})();
