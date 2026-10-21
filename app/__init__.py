from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
import re
from app.models.db import init_db, mongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    app = Flask(__name__)
    app.secret_key = "clave_secreta_fija"
    app.permanent_session_lifetime = timedelta(days=7)

    # Inicializar la base de datos NoSQL
    init_db(app)

    # Context processor: usuario disponible en todas las plantillas
    @app.context_processor
    def inject_user():
        usuario = None
        if 'usuario_id' in session:
            try:
                usuario = mongo.db.usuarios.find_one({"_id": ObjectId(session['usuario_id'])})
            except Exception as e:
                print("Error al convertir ObjectId:", e)
                session.pop('usuario_id', None)
        return dict(usuario=usuario)

   
   # -------------------------------
    # 🏠 Página principal con Buscador y Filtros
    # -------------------------------
    @app.route('/')
    def index():
        busqueda = request.args.get('q', '').strip()
        categoria = request.args.get('categoria', '').strip()

        # Construir el filtro dinámico para MongoDB
        filtro = {}
        if busqueda:
            # Buscar por título de forma insensible a mayúsculas/minúsculas usando expresiones regulares
            filtro['titulo'] = {"$regex": busqueda, "$options": "i"}
        
        if categoria and categoria != "Todas":
            filtro['categoria'] = categoria

        libros = list(mongo.db.libros.find(filtro))
        
        # Obtener categorías únicas para llenar el selector de filtros
        categorias = mongo.db.libros.distinct("categoria")

        return render_template('index.html', libros=libros, categorias=categorias, busqueda_actual=busqueda, categoria_actual=categoria)
    
    # -------------------------------
    # ✉️ Contacto: consultas de visitantes
    # -------------------------------
    @app.route('/contacto', methods=['GET', 'POST'])
    def contacto():
        if request.method == 'POST':
            nombre = request.form.get('nombre', '').strip()
            correo = request.form.get('correo', '').strip()
            asunto = request.form.get('asunto', '').strip()
            mensaje = request.form.get('mensaje', '').strip()

            # Validar los campos obligatorios
            if not all([nombre, correo, asunto, mensaje]):
                flash("Completa todos los campos del formulario.", "error")
                return render_template('contacto.html')

            # Validar longitudes
            if not (2 <= len(nombre) <= 100):
                flash("El nombre debe tener entre 2 y 100 caracteres.", "error")
                return render_template('contacto.html')

            if len(correo) > 254 or not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+", correo
            ):
                flash("Ingresa un correo electrónico válido.", "error")
                return render_template('contacto.html')

            if not (3 <= len(asunto) <= 120):
                flash("El asunto debe tener entre 3 y 120 caracteres.", "error")
                return render_template('contacto.html')

            if not (10 <= len(mensaje) <= 3000):
                flash("El mensaje debe tener entre 10 y 3000 caracteres.", "error")
                return render_template('contacto.html')

            # Guardar la consulta en una colección independiente
            consulta = {
                "nombre": nombre,
                "correo": correo,
                "asunto": asunto,
                "mensaje": mensaje,
                "fecha": datetime.utcnow(),
                "estado": "pendiente"
            }

            try:
                mongo.db.consultas_contacto.insert_one(consulta)
            except Exception:
                app.logger.exception(
                    "No se pudo guardar la consulta de contacto."
                )
                flash(
                    "No se pudo enviar tu consulta. "
                    "Inténtalo nuevamente más tarde.",
                    "error"
                )
                return render_template('contacto.html'), 500

            flash(
                "¡Tu consulta se envió correctamente! Gracias por contactarnos.",
                "success"
            )
            return redirect(url_for('contacto'))

        return render_template('contacto.html')

    
    # -------------------------------
    # 🔐 Login y Registro
    # -------------------------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            usuario = mongo.db.usuarios.find_one({"email": email})
            
            if usuario and check_password_hash(usuario.get('password'), password):
                session['usuario_id'] = str(usuario['_id'])
                session.permanent = True
                flash("¡Bienvenido de nuevo!", "success")
                return redirect(url_for('perfil'))
            else:
                flash("Credenciales incorrectas. Inténtalo de nuevo.", "error")
                return render_template('login.html')
        return render_template('login.html')

    @app.route('/registro', methods=['GET', 'POST'])
    def registro():
        if request.method == 'POST':
            email = request.form.get('email')
            if mongo.db.usuarios.find_one({"email": email}):
                flash("El correo electrónico ya está registrado.", "error")
                return render_template('registro.html')

            password_plana = request.form.get('password')
            password_cifrada = generate_password_hash(password_plana)

            nuevo_usuario = {
                "nombre": request.form.get('nombre'),
                "apellido": request.form.get('apellido'),
                "email": email,
                "password": password_cifrada,
                "telefono": "Sin registrar",
                "direccion": "Sin registrar",
                "rol": "CLIENTE",
                "activo": True
            }
            mongo.db.usuarios.insert_one(nuevo_usuario)
            flash("¡Registro exitoso! Ya puedes iniciar sesión.", "success")
            return redirect(url_for('login'))
        return render_template('registro.html')

    # -------------------------------
    # 🛒 Carrito y Pagos
    # -------------------------------
    @app.route('/carrito')
    def carrito():
        usuario_id = session.get('usuario_id')
        carrito_data = None
        if usuario_id:
            carrito_data = mongo.db.carritos.find_one({"usuario_id": ObjectId(usuario_id), "activo": True})
        return render_template('carrito.html', carrito=carrito_data)

    @app.route('/agregar_carrito/<libro_id>')
    def agregar_carrito(libro_id):
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            flash("Debes iniciar sesión para agregar libros al carrito.", "error")
            return redirect(url_for('login'))

        try:
            libro = mongo.db.libros.find_one({"_id": ObjectId(libro_id)})
        except Exception:
            return redirect(url_for('index'))

        if not libro:
            flash("El libro no existe.", "error")
            return redirect(url_for('index'))

        titulo = libro.get("titulo")
        precio = libro.get("precio", 0.0)
        stock_disponible = libro.get("stock", 0)

        carrito = mongo.db.carritos.find_one({"usuario_id": ObjectId(usuario_id), "activo": True})

        if not carrito:
            if stock_disponible < 1:
                flash(f"Lo sentimos, no hay stock disponible para '{titulo}'.", "error")
                return redirect(url_for('index'))

            nuevo_carrito = {
                "usuario_id": ObjectId(usuario_id),
                "items": [{
                    "titulo": titulo,
                    "precio_unitario": precio,
                    "cantidad": 1
                }],
                "activo": True
            }
            mongo.db.carritos.insert_one(nuevo_carrito)
        else:
            items = carrito.get("items", [])
            item_existente = next((item for item in items if item.get("titulo") == titulo), None)

            cantidad_actual_en_carrito = item_existente["cantidad"] if item_existente else 0

            # Validar que al sumar 1 no supere el stock
            if cantidad_actual_en_carrito + 1 > stock_disponible:
                flash(f"No puedes agregar más unidades. Stock máximo alcanzado para '{titulo}'.", "error")
                return redirect(url_for('carrito'))

            if item_existente:
                mongo.db.carritos.update_one(
                    {"_id": carrito["_id"], "items.titulo": titulo},
                    {"$inc": {"items.$.cantidad": 1}}
                )
            else:
                mongo.db.carritos.update_one(
                    {"_id": carrito["_id"]},
                    {"$push": {"items": {
                        "titulo": titulo,
                        "precio_unitario": precio,
                        "cantidad": 1
                    }}}
                )

        flash(f'Se agregó "{titulo}" a tu carrito.', "success")
        return redirect(url_for('carrito'))

    @app.route('/actualizar_carrito/<libro_titulo>', methods=['POST'])
    def actualizar_carrito(libro_titulo):
        usuario_id = session.get('usuario_id')
        cantidad = int(request.form.get('cantidad', 1))
        
        # Buscar el libro para conocer su stock real
        libro = mongo.db.libros.find_one({"titulo": libro_titulo})
        if not libro:
            flash("El libro ya no está disponible.", "error")
            return redirect(url_for('carrito'))

        stock_disponible = libro.get("stock", 0)

        if cantidad > stock_disponible:
            flash(f"Stock insuficiente. Solo hay {stock_disponible} unidades disponibles de '{libro_titulo}'.", "error")
            return redirect(url_for('carrito'))

        carrito = mongo.db.carritos.find_one({"usuario_id": ObjectId(usuario_id), "activo": True})
        if carrito:
            if cantidad > 0:
                mongo.db.carritos.update_one(
                    {"_id": carrito["_id"], "items.titulo": libro_titulo},
                    {"$set": {"items.$.cantidad": cantidad}}
                )
                flash("Carrito actualizado.", "success")
            else:
                mongo.db.carritos.update_one(
                    {"_id": carrito["_id"]},
                    {"$pull": {"items": {"titulo": libro_titulo}}}
                )
                flash(f'Se eliminó "{libro_titulo}" del carrito.', "success")
        return redirect(url_for('carrito'))

    @app.route('/eliminar_carrito/<libro_titulo>')
    def eliminar_carrito(libro_titulo):
        usuario_id = session.get('usuario_id')
        carrito = mongo.db.carritos.find_one({"usuario_id": ObjectId(usuario_id), "activo": True})
        if carrito:
            mongo.db.carritos.update_one(
                {"_id": carrito["_id"]},
                {"$pull": {"items": {"titulo": libro_titulo}}}
            )
            flash(f'Se eliminó "{libro_titulo}" del carrito.', "success")
        return redirect(url_for('carrito'))

    @app.route('/procesar_pago')
    def procesar_pago():
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return redirect(url_for('login'))

        usuario = mongo.db.usuarios.find_one({"_id": ObjectId(usuario_id)})
        carrito = mongo.db.carritos.find_one({"usuario_id": ObjectId(usuario_id), "activo": True})

        if not carrito or not carrito.get('items'):
            flash("Tu carrito está vacío.", "error")
            return redirect(url_for('carrito'))

        # Validación de stock antes de proceder
        for item in carrito['items']:
            libro = mongo.db.libros.find_one({"titulo": item['titulo']})
            if not libro or libro.get('stock', 0) < item['cantidad']:
                flash(f"Lo sentimos, no hay suficiente stock para '{item['titulo']}'.", "error")
                return redirect(url_for('carrito'))

        total = sum(item['cantidad'] * item['precio_unitario'] for item in carrito['items'])

        detalle = []
        for item in carrito['items']:
            libro = mongo.db.libros.find_one({"titulo": item['titulo']})
            
            if libro:
                mongo.db.libros.update_one(
                    {"_id": libro["_id"]},
                    {"$inc": {"stock": -item['cantidad']}}
                )

            detalle.append({
                "libro_id": libro['_id'] if libro else None,
                "titulo": item['titulo'],
                "cantidad": item['cantidad'],
                "precio_unitario": item['precio_unitario'],
                "subtotal": item['cantidad'] * item['precio_unitario']
            })

        nuevo_pedido = {
            "fecha": datetime.utcnow(),
            "estado": "COMPLETADO",
            "total": total,
            "usuario": {
                "usuario_id": ObjectId(usuario_id),
                "nombre": f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}".strip(),
                "email": usuario.get('email', '')
            },
            "detalle": detalle
        }
        mongo.db.pedidos.insert_one(nuevo_pedido)

        mongo.db.carritos.update_one(
            {"_id": carrito["_id"]},
            {"$set": {"activo": False}}
        )

        flash("¡Compra realizada con éxito! Revisa tu historial en el perfil.", "success")
        return redirect(url_for('perfil'))

    # -------------------------------
    # 👤 Perfil
    # -------------------------------
    @app.route('/perfil')
    def perfil():
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return redirect(url_for('login'))
        usuario = mongo.db.usuarios.find_one({"_id": ObjectId(usuario_id)})
        pedidos = list(mongo.db.pedidos.find({"usuario.usuario_id": ObjectId(usuario_id)}))
        return render_template('perfil.html', usuario=usuario, pedidos=pedidos)

    @app.route('/logout')
    def logout():
        session.pop('usuario_id', None)
        flash("Has cerrado sesión correctamente.", "success")
        return redirect(url_for('index'))

    return app