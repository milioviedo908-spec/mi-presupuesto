# Mi Presupuesto

App de presupuesto personal: repartís el sueldo entre gastos y ahorro, cargás categorías
con un tope cada una (marcadas como **activo** o **pasivo**), registrás gastos hasta llegar
al límite (después la app no te deja seguir cargando en esa categoría), y al cerrar el mes
se guarda un recuento en el historial.

## Estructura

```
presupuesto-app/
├── app.py              # Backend Flask + API + base de datos SQLite
├── requirements.txt
├── Procfile             # comando de arranque para Render
├── render.yaml           # config de despliegue automático en Render
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── app.js
```

## Correrla en tu computadora

Necesitás Python 3.10+ instalado.

```bash
cd presupuesto-app
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abrí `http://localhost:5000` en el navegador (o desde el celular, usando la IP de tu PC en la
misma red wifi, ej. `http://192.168.0.10:5000`).

## Subirla a GitHub

1. Creá un repositorio nuevo en GitHub (sin README, para no pisar el tuyo).
2. Desde la carpeta `presupuesto-app`:

```bash
git init
git add .
git commit -m "Primera versión de la app de presupuesto"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/TU-REPO.git
git push -u origin main
```

## Base de datos: por qué usar una externa

La app guarda todo en una base de datos real (vía SQLAlchemy). En tu compu usa un archivo
SQLite local y no necesitás configurar nada. Pero en el plan **gratuito** de Render el disco
del servicio es descartable: cada vez que el servicio se reinicia (y en el plan free se
reinicia seguido, por inactividad) se borraría un archivo SQLite guardado ahí. Los discos que
sí persisten en Render son solo para planes pagos.

La solución gratis y permanente es usar una base de datos Postgres externa. Recomiendo
[Neon](https://neon.tech): tiene un plan free sin vencimiento (a diferencia del Postgres
gratuito de Render, que expira a los 30 días).

1. Creá una cuenta en [neon.tech](https://neon.tech) y un proyecto nuevo.
2. Copiá el **Connection string** que te da (empieza con `postgresql://...`).
3. Esa URL es tu `DATABASE_URL`.

## Desplegarla en Render (queda accesible desde el celular)

1. Entrá a [render.com](https://render.com) y creá una cuenta (podés usar tu cuenta de GitHub).
2. Click en **New +** → **Blueprint**, y elegí el repositorio que acabás de subir. Render lee
   el `render.yaml` y configura el build y el start command solo.
   - Si preferís hacerlo a mano: **New +** → **Web Service**, elegís el repo, y completás:
     - Build command: `pip install -r requirements.txt`
     - Start command: `gunicorn app:app`
3. En **Environment** (dentro del servicio en Render), agregá la variable de entorno:
   - `DATABASE_URL` = la connection string que copiaste de Neon
4. Esperá a que termine el deploy (unos minutos). Render te da una URL pública tipo
   `https://mi-presupuesto.onrender.com`.
5. Esa URL funciona igual desde la compu, el celular o cualquier dispositivo — no hace falta
   instalar nada, es una página web normal, y ya está pensada para pantallas chicas.

### Nota sobre el plan gratuito de Render

El servicio "se duerme" después de un rato sin uso y tarda unos segundos en despertar la
próxima vez que entrás — es normal, no es un error. Como ahora los datos viven en Neon (no en
el disco del servicio), esos reinicios ya no te hacen perder información.

## Cómo funciona la lógica de límites

- Cada categoría tiene un `monto_asignado`. Cuando sumás un gasto, el backend valida que
  `gastado + nuevo_monto` no supere ese tope; si lo supera, devuelve un error y el frontend
  bloquea la carga (el botón pasa a "Límite alcanzado").
- Lo mismo pasa con el ahorro contra la meta mensual.
- Al tocar "Cerrar mes y guardar recuento", se guarda una foto completa del mes (categorías,
  gastado, ahorrado) en la tabla de historial, y se reinician los gastos/ahorros para arrancar
  el mes siguiente. Las categorías quedan iguales, así no las tenés que cargar de nuevo cada mes
  (si querés categorías distintas, las editás/eliminás antes de seguir cargando).
