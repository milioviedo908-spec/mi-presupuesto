from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# Base de datos: en producción usá una Postgres externa (ej. Neon, gratis y
# permanente) seteando la variable de entorno DATABASE_URL. En tu compu, si
# no la seteás, se usa un archivo SQLite local (presupuesto.db).
db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'presupuesto.db'))
if db_url.startswith('postgres://'):  # algunos proveedores dan la URL con el prefijo viejo
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
db = SQLAlchemy(app)


# ---------- Modelos ----------

class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sueldo = db.Column(db.Float, nullable=False, default=0)
    monto_gastos = db.Column(db.Float, nullable=False, default=0)
    monto_ahorro = db.Column(db.Float, nullable=False, default=0)

    def to_dict(self):
        return {'id': self.id, 'sueldo': self.sueldo,
                'monto_gastos': self.monto_gastos, 'monto_ahorro': self.monto_ahorro}


class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'activo' o 'pasivo'
    monto_asignado = db.Column(db.Float, nullable=False, default=0)
    activa = db.Column(db.Boolean, nullable=False, default=True)
    gastos = db.relationship('Gasto', backref='categoria', cascade='all, delete-orphan')

    def gastado(self):
        return sum(g.monto for g in self.gastos)

    def to_dict(self):
        gastado = self.gastado()
        return {'id': self.id, 'nombre': self.nombre, 'tipo': self.tipo,
                'monto_asignado': self.monto_asignado, 'gastado': gastado,
                'disponible': self.monto_asignado - gastado}


class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.String(40), nullable=False)


class Ahorro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.String(40), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'monto': self.monto, 'descripcion': self.descripcion, 'fecha': self.fecha}


class Cierre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.String(20), nullable=False)
    fecha_cierre = db.Column(db.String(40), nullable=False)
    resumen_json = db.Column(db.Text, nullable=False)


class Ingreso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.String(40), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'monto': self.monto, 'descripcion': self.descripcion, 'fecha': self.fecha}


class Deuda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    monto_total = db.Column(db.Float, nullable=False)
    monto_pagado = db.Column(db.Float, nullable=False, default=0)
    fecha_vencimiento = db.Column(db.String(20))  # 'YYYY-MM-DD', opcional
    fecha_creacion = db.Column(db.String(40), nullable=False)
    activa = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        pendiente = self.monto_total - self.monto_pagado
        vencida = False
        if self.fecha_vencimiento and pendiente > 1e-9:
            vencida = self.fecha_vencimiento < datetime.now().strftime('%Y-%m-%d')
        return {'id': self.id, 'nombre': self.nombre, 'monto_total': self.monto_total,
                'monto_pagado': self.monto_pagado, 'pendiente': pendiente,
                'fecha_vencimiento': self.fecha_vencimiento, 'vencida': vencida,
                'saldada': pendiente <= 1e-9}


with app.app_context():
    db.create_all()
    if db.session.get(Config, 1) is None:
        db.session.add(Config(id=1, sueldo=0, monto_gastos=0, monto_ahorro=0))
        db.session.commit()


# ---------- Páginas ----------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- Config ----------

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(db.session.get(Config, 1).to_dict())


@app.route('/api/config', methods=['POST'])
def set_config():
    data = request.get_json(force=True)
    try:
        sueldo = float(data.get('sueldo', 0))
        monto_gastos = float(data.get('monto_gastos', 0))
        monto_ahorro = float(data.get('monto_ahorro', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Los montos deben ser números'}), 400
    cfg = db.session.get(Config, 1)
    cfg.sueldo, cfg.monto_gastos, cfg.monto_ahorro = sueldo, monto_gastos, monto_ahorro
    db.session.commit()
    return jsonify({'ok': True})


# ---------- Categorías ----------

@app.route('/api/categorias', methods=['GET'])
def get_categorias():
    cats = Categoria.query.filter_by(activa=True).order_by(Categoria.id).all()
    return jsonify([c.to_dict() for c in cats])


@app.route('/api/categorias', methods=['POST'])
def add_categoria():
    data = request.get_json(force=True)
    nombre = (data.get('nombre') or '').strip()
    tipo = data.get('tipo')
    try:
        monto_asignado = float(data.get('monto_asignado', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto asignado debe ser un número'}), 400
    if not nombre or tipo not in ('activo', 'pasivo') or monto_asignado <= 0:
        return jsonify({'error': 'Completá nombre, tipo y un monto asignado mayor a 0'}), 400
    db.session.add(Categoria(nombre=nombre, tipo=tipo, monto_asignado=monto_asignado, activa=True))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/categorias/<int:cat_id>', methods=['DELETE'])
def delete_categoria(cat_id):
    cat = db.session.get(Categoria, cat_id)
    if cat:
        cat.activa = False
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Gastos ----------

@app.route('/api/gastos', methods=['POST'])
def add_gasto():
    data = request.get_json(force=True)
    categoria_id = data.get('categoria_id')
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    descripcion = (data.get('descripcion') or '').strip()
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    cat = Categoria.query.filter_by(id=categoria_id, activa=True).first()
    if not cat:
        return jsonify({'error': 'Esa categoría no existe'}), 404
    gastado = cat.gastado()
    if gastado + monto > cat.monto_asignado + 1e-9:
        disponible = cat.monto_asignado - gastado
        return jsonify({'error': f'Llegaste al límite de "{cat.nombre}". Disponible: ${disponible:,.2f}'}), 400
    db.session.add(Gasto(categoria_id=categoria_id, monto=monto, descripcion=descripcion,
                          fecha=datetime.now().isoformat()))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/gastos/<int:gasto_id>', methods=['DELETE'])
def delete_gasto(gasto_id):
    gasto = db.session.get(Gasto, gasto_id)
    if gasto:
        db.session.delete(gasto)
        db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/gastos', methods=['GET'])
def list_gastos():
    rows = db.session.query(Gasto, Categoria).join(Categoria).order_by(Gasto.fecha.desc()).all()
    return jsonify([{'id': g.id, 'monto': g.monto, 'descripcion': g.descripcion, 'fecha': g.fecha,
                      'categoria': c.nombre, 'tipo': c.tipo} for g, c in rows])


# ---------- Ahorro ----------

@app.route('/api/ahorros', methods=['GET'])
def get_ahorros():
    rows = Ahorro.query.order_by(Ahorro.fecha.desc()).all()
    total = sum(a.monto for a in rows)
    return jsonify({'items': [a.to_dict() for a in rows], 'total': total})


@app.route('/api/ahorros', methods=['POST'])
def add_ahorro():
    data = request.get_json(force=True)
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    descripcion = (data.get('descripcion') or '').strip()
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    cfg = db.session.get(Config, 1)
    total = sum(a.monto for a in Ahorro.query.all())
    if total + monto > cfg.monto_ahorro + 1e-9:
        disponible = cfg.monto_ahorro - total
        return jsonify({'error': f'Llegaste a la meta de ahorro. Disponible: ${disponible:,.2f}'}), 400
    db.session.add(Ahorro(monto=monto, descripcion=descripcion, fecha=datetime.now().isoformat()))
    db.session.commit()
    return jsonify({'ok': True})


# ---------- Ingresos (sueldo, etc) ----------

@app.route('/api/ingresos', methods=['GET'])
def get_ingresos():
    rows = Ingreso.query.order_by(Ingreso.fecha.desc()).all()
    total = sum(i.monto for i in rows)
    return jsonify({'items': [i.to_dict() for i in rows], 'total': total})


@app.route('/api/ingresos', methods=['POST'])
def add_ingreso():
    data = request.get_json(force=True)
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    descripcion = (data.get('descripcion') or '').strip()
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    db.session.add(Ingreso(monto=monto, descripcion=descripcion, fecha=datetime.now().isoformat()))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/ingresos/<int:ingreso_id>', methods=['DELETE'])
def delete_ingreso(ingreso_id):
    ingreso = db.session.get(Ingreso, ingreso_id)
    if ingreso:
        db.session.delete(ingreso)
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Deudas ----------

@app.route('/api/deudas', methods=['GET'])
def get_deudas():
    rows = Deuda.query.filter_by(activa=True).order_by(Deuda.fecha_vencimiento.asc().nulls_last()).all()
    deudas = [d.to_dict() for d in rows]
    return jsonify(deudas)


@app.route('/api/deudas', methods=['POST'])
def add_deuda():
    data = request.get_json(force=True)
    nombre = (data.get('nombre') or '').strip()
    fecha_vencimiento = (data.get('fecha_vencimiento') or '').strip() or None
    try:
        monto_total = float(data.get('monto_total', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    if not nombre or monto_total <= 0:
        return jsonify({'error': 'Completá nombre y un monto mayor a 0'}), 400
    db.session.add(Deuda(nombre=nombre, monto_total=monto_total, monto_pagado=0,
                          fecha_vencimiento=fecha_vencimiento, fecha_creacion=datetime.now().isoformat(),
                          activa=True))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/deudas/<int:deuda_id>/pago', methods=['POST'])
def pagar_deuda(deuda_id):
    data = request.get_json(force=True)
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    deuda = db.session.get(Deuda, deuda_id)
    if not deuda or not deuda.activa:
        return jsonify({'error': 'Esa deuda no existe'}), 404
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    deuda.monto_pagado = min(deuda.monto_total, deuda.monto_pagado + monto)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/deudas/<int:deuda_id>', methods=['DELETE'])
def delete_deuda(deuda_id):
    deuda = db.session.get(Deuda, deuda_id)
    if deuda:
        deuda.activa = False
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Resumen y cierre ----------

def _resumen_dict():
    cfg = db.session.get(Config, 1)
    cats = Categoria.query.filter_by(activa=True).all()
    detalle = []
    total_asignado = total_gastado = 0.0
    activos_asig = activos_gast = 0.0
    pasivos_asig = pasivos_gast = 0.0
    for cat in cats:
        gastado = cat.gastado()
        detalle.append({'nombre': cat.nombre, 'tipo': cat.tipo,
                         'asignado': cat.monto_asignado, 'gastado': gastado})
        total_asignado += cat.monto_asignado
        total_gastado += gastado
        if cat.tipo == 'activo':
            activos_asig += cat.monto_asignado
            activos_gast += gastado
        else:
            pasivos_asig += cat.monto_asignado
            pasivos_gast += gastado
    total_ahorrado = sum(a.monto for a in Ahorro.query.all())
    total_ingresos = sum(i.monto for i in Ingreso.query.all())
    return {
        'config': cfg.to_dict(),
        'detalle': detalle,
        'total_asignado': total_asignado,
        'total_gastado': total_gastado,
        'activos': {'asignado': activos_asig, 'gastado': activos_gast},
        'pasivos': {'asignado': pasivos_asig, 'gastado': pasivos_gast},
        'ahorro': {'meta': cfg.monto_ahorro, 'ahorrado': total_ahorrado},
        'ingresos_total': total_ingresos,
    }


@app.route('/api/resumen', methods=['GET'])
def resumen():
    return jsonify(_resumen_dict())


@app.route('/api/cerrar_mes', methods=['POST'])
def cerrar_mes():
    data = request.get_json(force=True, silent=True) or {}
    mes = data.get('mes') or datetime.now().strftime('%Y-%m')
    import json
    resumen_data = _resumen_dict()
    db.session.add(Cierre(mes=mes, fecha_cierre=datetime.now().isoformat(),
                           resumen_json=json.dumps(resumen_data)))
    Gasto.query.delete()
    Ahorro.query.delete()
    Ingreso.query.delete()  # las deudas NO se borran: siguen hasta saldarse
    db.session.commit()
    return jsonify({'ok': True, 'resumen': resumen_data})


@app.route('/api/historial', methods=['GET'])
def historial():
    import json
    rows = Cierre.query.order_by(Cierre.fecha_cierre.desc()).all()
    return jsonify([{'id': r.id, 'mes': r.mes, 'fecha_cierre': r.fecha_cierre,
                      'resumen': json.loads(r.resumen_json)} for r in rows])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    
        
    



      
        




        
    


