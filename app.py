from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
from helpers import apology, login_required, lookup, usd
import uuid
from werkzeug.utils import secure_filename
import os


# Configure application
app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if __name__ == "__main__":
    app.run(debug=True)

# Database connection
conn = psycopg2.connect(
    dbname="kawok",
    user="postgres",
    password="12345",
    host="127.0.0.1",
    port="5432"
)

# Create a cursor to execute SQL commands
cur = conn.cursor()


@app.route("/")
def index():
    """Show homepage"""
    if session.get("user_id"):
        return redirect("/home")
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        user = request.form.get("username")
        password = request.form.get("password")
        if not user:
            return apology("Debes proveer un usuario", 400)

        # Ensure password was submitted
        if not password:
            return apology("Debes proveer una contraseña", 400)

        # Query database for username
        cur.execute(
            "SELECT * FROM usuarios WHERE usuario = %s", (user,)
        )
        rows = cur.fetchall()

        

        # Ensure user and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0][3], password
        ):
            return apology("Contraseña o usuario inválidos.", 400)


        # Remember which user has logged in
        session["user_id"] = rows[0][0]
        session["username"] = rows[0][2]
        
        cur.execute("SELECT 1 FROM artists WHERE id_usuario = %s", (session["user_id"],))
        if cur.fetchone():
            session["register_user_type"] = "artista"
        else:
            session["register_user_type"] = "venue"

        # Redirect user to home page
        return redirect("/home")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/clear_session")
def clear_session():
    session.clear()
    return "Sesión limpiada"


@app.route("/register", methods=["GET", "POST"])
def register():
    # In your /register route (after POST)
    session["register_user_type"] = request.form.get("user_type")
    user_type = session.get("register_user_type", "artista")

    if request.method == "POST":
        print("POST data:", request.form)
        if user_type not in ["artista", "venue"]:
            return apology("Debes seleccionar un tipo de usuario", 400)

        if not request.form.get("nombre"):
            return apology("Debes proporcionar un nombre", 400)

        if not request.form.get("usuario"):
            return apology("Debes proporcionar un nombre de usuario", 400)

        if not request.form.get("correo"):
            return apology("Debes proporcionar un correo electrónico", 400)

        if not request.form.get("contraseña"):
            return apology("Debes proporcionar una contraseña", 400)

        if not request.form.get("confirmar"):
            return apology("Debes proporcionar una confirmación de contraseña", 400)
        # Check if username or email already exists
        cur.execute("SELECT * FROM usuarios WHERE usuario = %s OR correo = %s",
                    (request.form.get("usuario"), request.form.get("correo")))
        if cur.fetchone():
            return apology("El nombre de usuario o el correo electrónico ya existen", 400)

        # Validate passwords
        if request.form.get("contraseña") != request.form.get("confirmar"):
            return apology("Las contraseñas deben coincidir", 400)
        # Insert new user into the database
        session["register_step1"] = {
        "user_type": request.form.get("user_type"),
        "nombre": request.form.get("nombre"),
        "usuario": request.form.get("usuario"),
        "correo": request.form.get("correo"),
        "contraseña": request.form.get("contraseña"),
        "confirmar": request.form.get("confirmar"),
    }

        return redirect("/register2")
    datos = session.get("register_step1", {})
    return render_template("register.html", datos=datos, user_type=user_type)

@app.route("/register2", methods=["GET", "POST"])
def register2():
    user_type = session.get("register_user_type", "artista")
    cur.execute("SELECT * FROM ciudades")
    ciudades = cur.fetchall()

    cur.execute("SELECT * FROM generos")
    generos = cur.fetchall()

    if request.method == "POST":
        print("POST data:", request.form)
        print("user_type:", user_type)
        # Validate required fields
        if not request.form.get("telefono"):
            return apology("Debes proporcionar un número de teléfono", 400)
        if not request.form.get("ciudad"):
            return apology("Debes seleccionar una ciudad", 400)
        
        if user_type == "artista":
            if not request.form.get("dui"):
                return apology("Debes proporcionar un número de DUI", 400)
            if not request.form.get("nombre_artista"):
                return apology("Debes proporcionar un nombre artístico", 400)
            if not request.form.get("genero"):
                return apology("Debes seleccionar un género", 400)
            
        else:  # user_type == "venue"
            if not request.form.get("nit"):
                return apology("Debes proporcionar un NIT", 400)
            if not request.form.get("nombre_venue"):
                return apology("Debes proporcionar un nombre de venue", 400)
            if not request.form.get("direccion"):
                return apology("Debes proporcionar una dirección del venue", 400)

        if user_type == "artista":
            session["register_step2"] = {
                "telefono": request.form.get("telefono"),
                "ciudad": request.form.get("ciudad"),
                "dui": request.form.get("dui"),
                "nombre_artista": request.form.get("nombre_artista"),
                "genero": request.form.get("genero"),
            }
        else:
            session["register_step2"] = {
                "telefono": request.form.get("telefono"),
                "ciudad": request.form.get("ciudad"),
                "nit": request.form.get("nit"),
                "nombre_venue": request.form.get("nombre_venue"),
                "direccion": request.form.get("direccion"),
            }
        
        
        return redirect("/register3")
    datos_usuario = session.get("register_step2", {})
    return render_template("register2.html", datos_usuario=datos_usuario, user_type=user_type, ciudades=ciudades, generos=generos)

@app.route("/register3", methods=["GET", "POST"])
def register3():
    print("register_step1:", session.get("register_step1"))
    print("register_user_type:", session.get("register_user_type"))
    user_type = session.get("register_user_type", "artista")
    if request.method == "POST":
        # Validiate required fields
        if not request.form.get("fee_range"):
            return apology("Debes proporcionar un rango de fee", 400)
        if not request.form.get("descripcion"):
            return apology("Debes proporcionar una descripción", 400)
        if "image_upload" not in request.files or request.files["image_upload"].filename == "":
            return apology("Debes proporcionar una foto", 400)
        
        # Save the uploaded image
        image = request.files["image_upload"]
        if image and image.filename != "":
            ext = os.path.splitext(secure_filename(image.filename))[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            # Elige la subcarpeta según el tipo de usuario
            if user_type == "artista":
                subfolder = "artistas"
            else:
                subfolder = "venues"
            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder)
            os.makedirs(folder_path, exist_ok=True)  # Crea la carpeta si no existe
            image_path = os.path.join(folder_path, unique_name)
            image.save(image_path)
            image_db_path = f"uploads/{subfolder}/{unique_name}"
        else:
            image_db_path = None

        if user_type == "artista":
            session["register_step3"] = {
                "fee_range": request.form.get("fee_range"),
                "descripcion": request.form.get("descripcion"),
                "image_upload": image_db_path,
            }
        else:  # user_type == "venue"
            session["register_step3"] = {
                "fee_range": request.form.get("fee_range"),
                "descripcion": request.form.get("descripcion"),
                "image_upload": image_db_path,
            }

        # Insert user into the database y obtener el id generado
        cur.execute(
            "INSERT INTO USUARIOS (nombre, usuario, contraseña, correo, telefono, id_ciudad) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                session["register_step1"]["nombre"],
                session["register_step1"]["usuario"],
                generate_password_hash(session["register_step1"]["contraseña"]),
                session["register_step1"]["correo"],
                session["register_step2"]["telefono"],
                session["register_step2"]["ciudad"]
            )
        )
        user_id = cur.fetchone()[0] 

        user_type = session.get("register_user_type", "artista")

        if user_type == "artista":
            cur.execute(
                "INSERT INTO artists (nombre_artista, id_usuario, id_genero, fee_max, descripcion_artista, imagen_artista, dui)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    session["register_step2"]["nombre_artista"],
                    user_id, 
                    session["register_step2"]["genero"],
                    session["register_step3"]["fee_range"],
                    session["register_step3"]["descripcion"],
                    session["register_step3"]["image_upload"],
                    session["register_step2"]["dui"]
                )
            )
        else:  # user_type == "venue"
            cur.execute(
                "INSERT INTO venues (nombre_venue, nit, direccion, pago_max, id_usuario, descripcion_venue, imagen_venue)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    session["register_step2"]["nombre_venue"],
                    session["register_step2"]["nit"],
                    session["register_step2"]["direccion"],
                    session["register_step3"]["fee_range"],
                    user_id,
                    session["register_step3"]["descripcion"],
                    session["register_step3"]["image_upload"]
                )
            )
        conn.commit()
        # Clear the session data after successful registration
        session.pop("register_step1", None)
        session.pop("register_step2", None)
        session.pop("register_step3", None)
        return redirect("/login")
    datos_usuario = session.get("register_step3", {})
    return render_template("register3.html", user_type=user_type, datos_usuario=datos_usuario)


@app.route("/home")
@login_required
def home():
    user_type = session.get("register_user_type", "artista")
    if user_type == "artista":
        cur.execute("SELECT nombre_venue, imagen_venue FROM venues")
        cards = cur.fetchall()
    else:
        cur.execute("SELECT nombre_artista, imagen_artista FROM artists")
        cards = cur.fetchall()
    return render_template("home.html", user_type=user_type, cards=cards)

@app.route("/discover")
@login_required
def discover():
    user_type = session.get("register_user_type", "artista")
    search = request.args.get("q", "").strip()
    if user_type == "artista":
        if search:
            cur.execute("SELECT * FROM venues WHERE LOWER(nombre_venue) LIKE %s", (f"%{search.lower()}%",))
        else:
            cur.execute("SELECT * FROM venues")
        cards = cur.fetchall()
    else:
        if search:
            cur.execute("SELECT * FROM artists a JOIN generos b ON a.id_genero = b.id WHERE LOWER(a.nombre_artista) LIKE %s", (f"%{search.lower()}%",))
        else:
            cur.execute("SELECT * FROM artists a JOIN generos b ON a.id_genero = b.id")
        cards = cur.fetchall()
    return render_template("discover.html", user_type=user_type, cards=cards)

@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", username=session.get("username"))

