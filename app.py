from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-de-desarrollo-cambiar-en-produccion')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'presupuesto.db'))
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Iniciá sesión para continuar.'
login_manager.login_message_category = 'error'


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Sesión vencida, iniciá sesión de nuevo.'}), 401
    return redirect(url_for('login'))


# ---------- Modelos ----------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    fecha_creacion = db.Column(db.String(40), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    sueldo = db.Column(db.Float, nullable=False, default=0)
    monto_gastos = db.Column(db.Float, nullable=False, default=0)
    monto_ahorro = db.Column(db.Float, nullable=False, default=0)

    def to_dict(self):
        return {'sueldo': self.sueldo, 'monto_gastos': self.monto_gastos, 'monto_ahorro': self.monto_ahorro}


class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.String(40), nullable=False)


class Ahorro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.String(40), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'monto': self.monto, 'descripcion': self.descripcion, 'fecha': self.fecha}


class Ingreso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.String(40), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'monto': self.monto, 'descripcion': self.descripcion, 'fecha': self.fecha}


class Deuda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    monto_total = db.Column(db.Float, nullable=False)
    monto_pagado = db.Column(db.Float, nullable=False, default=0)
    fecha_vencimiento = db.Column(db.String(20))
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


class Cierre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    fecha_cierre = db.Column(db.String(40), nullable=False)
    resumen_json = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()


def get_or_create_config():
    cfg = Config.query.filter_by(user_id=current_user.id).first()
    if not cfg:
        cfg = Config(user_id=current_user.id, sueldo=0, monto_gastos=0, monto_ahorro=0)
        db.session.add(cfg)
        db.session.commit()
    return cfg


# ---------- Autenticación ----------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirmar = request.form.get('confirmar') or ''
        if not email or '@' not in email:
            error = 'Ingresá un email válido.'
        elif len(password) < 6:
            error = 'La contraseña tiene que tener al menos 6 caracteres.'
        elif password != confirmar:
            error = 'Las contraseñas no coinciden.'
        elif User.query.filter_by(email=email).first():
            error = 'Ya existe una cuenta con ese email.'
        else:
            user = User(email=email, fecha_creacion=datetime.now().isoformat())
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        error = 'Email o contraseña incorrectos.'
    return render_template('login.html', error=error)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------- Página principal ----------

@app.route('/')
@login_required
def index():
    return render_template('index.html', user_email=current_user.email)


# ---------- Config ----------

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    return jsonify(get_or_create_config().to_dict())


@app.route('/api/config', methods=['POST'])
@login_required
def set_config():
    data = request.get_json(force=True)
    try:
        sueldo = float(data.get('sueldo', 0))
        monto_gastos = float(data.get('monto_gastos', 0))
        monto_ahorro = float(data.get('monto_ahorro', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Los montos deben ser números'}), 400
    cfg = get_or_create_config()
    cfg.sueldo, cfg.monto_gastos, cfg.monto_ahorro = sueldo, monto_gastos, monto_ahorro
    db.session.commit()
    return jsonify({'ok': True})


# ---------- Categorías ----------

@app.route('/api/categorias', methods=['GET'])
@login_required
def get_categorias():
    cats = Categoria.query.filter_by(user_id=current_user.id, activa=True).order_by(Categoria.id).all()
    return jsonify([c.to_dict() for c in cats])


@app.route('/api/categorias', methods=['POST'])
@login_required
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
    db.session.add(Categoria(user_id=current_user.id, nombre=nombre, tipo=tipo,
                              monto_asignado=monto_asignado, activa=True))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/categorias/<int:cat_id>', methods=['DELETE'])
@login_required
def delete_categoria(cat_id):
    cat = Categoria.query.filter_by(id=cat_id, user_id=current_user.id).first()
    if cat:
        cat.activa = False
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Gastos ----------

@app.route('/api/gastos', methods=['POST'])
@login_required
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
    cat = Categoria.query.filter_by(id=categoria_id, user_id=current_user.id, activa=True).first()
    if not cat:
        return jsonify({'error': 'Esa categoría no existe'}), 404
    gastado = cat.gastado()
    if gastado + monto > cat.monto_asignado + 1e-9:
        disponible = cat.monto_asignado - gastado
        return jsonify({'error': f'Llegaste al límite de "{cat.nombre}". Disponible: ${disponible:,.2f}'}), 400
    db.session.add(Gasto(user_id=current_user.id, categoria_id=categoria_id, monto=monto,
                          descripcion=descripcion, fecha=datetime.now().isoformat()))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/gastos/<int:gasto_id>', methods=['DELETE'])
@login_required
def delete_gasto(gasto_id):
    gasto = Gasto.query.filter_by(id=gasto_id, user_id=current_user.id).first()
    if gasto:
        db.session.delete(gasto)
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Ahorro ----------

@app.route('/api/ahorros', methods=['GET'])
@login_required
def get_ahorros():
    rows = Ahorro.query.filter_by(user_id=current_user.id).order_by(Ahorro.fecha.desc()).all()
    total = sum(a.monto for a in rows)
    return jsonify({'items': [a.to_dict() for a in rows], 'total': total})


@app.route('/api/ahorros', methods=['POST'])
@login_required
def add_ahorro():
    data = request.get_json(force=True)
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    descripcion = (data.get('descripcion') or '').strip()
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    cfg = get_or_create_config()
    total = sum(a.monto for a in Ahorro.query.filter_by(user_id=current_user.id).all())
    if total + monto > cfg.monto_ahorro + 1e-9:
        disponible = cfg.monto_ahorro - total
        return jsonify({'error': f'Llegaste a la meta de ahorro. Disponible: ${disponible:,.2f}'}), 400
    db.session.add(Ahorro(user_id=current_user.id, monto=monto, descripcion=descripcion,
                           fecha=datetime.now().isoformat()))
    db.session.commit()
    return jsonify({'ok': True})


# ---------- Ingresos ----------

@app.route('/api/ingresos', methods=['GET'])
@login_required
def get_ingresos():
    rows = Ingreso.query.filter_by(user_id=current_user.id).order_by(Ingreso.fecha.desc()).all()
    total = sum(i.monto for i in rows)
    return jsonify({'items': [i.to_dict() for i in rows], 'total': total})


@app.route('/api/ingresos', methods=['POST'])
@login_required
def add_ingreso():
    data = request.get_json(force=True)
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    descripcion = (data.get('descripcion') or '').strip()
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    db.session.add(Ingreso(user_id=current_user.id, monto=monto, descripcion=descripcion,
                            fecha=datetime.now().isoformat()))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/ingresos/<int:ingreso_id>', methods=['DELETE'])
@login_required
def delete_ingreso(ingreso_id):
    ingreso = Ingreso.query.filter_by(id=ingreso_id, user_id=current_user.id).first()
    if ingreso:
        db.session.delete(ingreso)
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Deudas ----------

@app.route('/api/deudas', methods=['GET'])
@login_required
def get_deudas():
    rows = Deuda.query.filter_by(user_id=current_user.id, activa=True) \
        .order_by(Deuda.fecha_vencimiento.asc().nulls_last()).all()
    return jsonify([d.to_dict() for d in rows])


@app.route('/api/deudas', methods=['POST'])
@login_required
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
    db.session.add(Deuda(user_id=current_user.id, nombre=nombre, monto_total=monto_total, monto_pagado=0,
                          fecha_vencimiento=fecha_vencimiento, fecha_creacion=datetime.now().isoformat(),
                          activa=True))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/deudas/<int:deuda_id>/pago', methods=['POST'])
@login_required
def pagar_deuda(deuda_id):
    data = request.get_json(force=True)
    try:
        monto = float(data.get('monto', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'El monto debe ser un número'}), 400
    deuda = Deuda.query.filter_by(id=deuda_id, user_id=current_user.id, activa=True).first()
    if not deuda:
        return jsonify({'error': 'Esa deuda no existe'}), 404
    if monto <= 0:
        return jsonify({'error': 'El monto tiene que ser mayor a 0'}), 400
    deuda.monto_pagado = min(deuda.monto_total, deuda.monto_pagado + monto)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/deudas/<int:deuda_id>', methods=['DELETE'])
@login_required
def delete_deuda(deuda_id):
    deuda = Deuda.query.filter_by(id=deuda_id, user_id=current_user.id).first()
    if deuda:
        deuda.activa = False
        db.session.commit()
    return jsonify({'ok': True})


# ---------- Resumen y cierre ----------

def _resumen_dict():
    cfg = get_or_create_config()
    cats = Categoria.query.filter_by(user_id=current_user.id, activa=True).all()
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
    total_ahorrado = sum(a.monto for a in Ahorro.query.filter_by(user_id=current_user.id).all())
    total_ingresos = sum(i.monto for i in Ingreso.query.filter_by(user_id=current_user.id).all())
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
@login_required
def resumen():
    return jsonify(_resumen_dict())


@app.route('/api/cerrar_mes', methods=['POST'])
@login_required
def cerrar_mes():
    data = request.get_json(force=True, silent=True) or {}
    mes = data.get('mes') or datetime.now().strftime('%Y-%m')
    import json
    resumen_data = _resumen_dict()
    db.session.add(Cierre(user_id=current_user.id, mes=mes, fecha_cierre=datetime.now().isoformat(),
                           resumen_json=json.dumps(resumen_data)))
    Gasto.query.filter_by(user_id=current_user.id).delete()
    Ahorro.query.filter_by(user_id=current_user.id).delete()
    Ingreso.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'ok': True, 'resumen': resumen_data})


@app.route('/api/historial', methods=['GET'])
@login_required
def historial():
    import json
    rows = Cierre.query.filter_by(user_id=current_user.id).order_by(Cierre.fecha_cierre.desc()).all()
    return jsonify([{'id': r.id, 'mes': r.mes, 'fecha_cierre': r.fecha_cierre,
                      'resumen': json.loads(r.resumen_json)} for r in rows])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

