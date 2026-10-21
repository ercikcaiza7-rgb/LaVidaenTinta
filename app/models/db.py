from flask_pymongo import PyMongo

# Inicializamos la extensión de MongoDB
mongo = PyMongo()

def init_db(app):
    # Conectamos con tu base de datos llamada 'Libreria' en el puerto local de MongoDB
    app.config["MONGO_URI"] = "mongodb://localhost:27017/Libreria"
    mongo.init_app(app)
    return mongo