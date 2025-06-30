from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
from helpers import apology, login_required, lookup, usd
import uuid
from werkzeug.utils import secure_filename
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
bucket_name = os.environ.get("SUPABASE_BUCKET")

supabase: Client = create_client(supabase_url, supabase_key)

def upload_to_supabase_storage(file, storage_path):
    # file: FileStorage (werkzeug)
    # storage_path: str, e.g. "artistas/123456.jpg"
    resp = supabase.storage.from_(bucket_name).upload(storage_path, file, file.content_type)
    if "error" in resp and resp["error"]:
        raise Exception("Error al subir archivo a Supabase: " + str(resp["error"]))
    # La url pública puede variar según política del bucket (hazla pública desde el panel de Supabase para facilidad)
    public_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
    return public_url


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
conn = psycopg2.connect(os.environ["DATABASE_URL"])
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
            if user_type == "artista":
                storage_path = f"artistas/{unique_name}"
            else:
                storage_path = f"venues/{unique_name}"
            public_url = upload_to_supabase_storage(image, storage_path)
            image_db_path = public_url  # Así guardas la URL accesible
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
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    user_type = session.get("register_user_type", "artista")
    if user_type == "artista":
        cur.execute("SELECT nombre_venue, imagen_venue FROM venues")
        cards = cur.fetchall()

        cur.execute("SELECT id FROM artists WHERE id_usuario = %s", (user_id,))
        artist_row = cur.fetchone()
        artist_id = artist_row[0] if artist_row else None

        # Get accepted bookings for artist
        cur.execute("""
            SELECT s.id, v.nombre_venue, v.direccion, t.fecha, t.hora_inicio, t.hora_fin, v.imagen_venue, u.telefono
            FROM solicitudes s
            JOIN venues v ON s.id_venue = v.id
            JOIN usuarios u ON v.id_usuario = u.id
            JOIN toques t ON s.id_toque = t.id
            WHERE s.id_artista = %s AND s.estado = 'aceptado'
            ORDER BY t.fecha, t.hora_inicio
        """, (artist_id,))
        bookings = cur.fetchall()
    else:
        cur.execute("SELECT nombre_artista, imagen_artista FROM artists")
        cards = cur.fetchall()
        
        cur.execute("SELECT id FROM venues WHERE id_usuario = %s", (user_id,))
        venue_row = cur.fetchone()
        venue_id = venue_row[0] if venue_row else None

        # Get accepted bookings for venue
        cur.execute("""
            SELECT s.id, a.nombre_artista, a.descripcion_artista, t.fecha, t.hora_inicio, t.hora_fin, a.imagen_artista, u.telefono
            FROM solicitudes s
            JOIN artists a ON s.id_artista = a.id
            JOIN usuarios u ON a.id_usuario = u.id
            JOIN toques t ON s.id_toque = t.id
            WHERE s.id_venue = %s AND s.estado = 'aceptado'
            ORDER BY t.fecha, t.hora_inicio
        """, (venue_id,))
        bookings = cur.fetchall()

    return render_template("home.html", user_type=user_type, cards=cards, bookings=bookings)

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

    cur.execute("SELECT telefono FROM usuarios a JOIN artists b ON a.id = b.id_usuario")
    telefono = cur.fetchall()
    return render_template("discover.html", user_type=user_type, cards=cards, telefono=telefono)

@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", username=session.get("username"))



@app.route("/book/<int:venue_id>", methods=["GET", "POST"])
@login_required
def book(venue_id):
    if request.method == "POST":
        user_id = session.get("user_id")
        if not user_id:
            return apology("You must be logged in to book a venue", 403)

        # Get artist id from user_id
        cur.execute("SELECT id FROM artists WHERE id_usuario = %s", (user_id,))
        artist_row = cur.fetchone()
        if not artist_row:
            return apology("No artist profile found.", 400)
        id_artista = artist_row[0]

        # Get date and time from form
        fecha_hora = request.form.get("fecha")  # e.g. "2025-07-01 18:00"
        if not fecha_hora:
            return apology("Debes seleccionar una fecha y hora", 400)

        # Parse date and hour
        from datetime import datetime, timedelta
        dt = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M")
        fecha = dt.date()
        hora_inicio = dt.time()
        hora_fin = (dt + timedelta(hours=1)).time()  # 1-hour block

        # Insert into toques
        cur.execute(
            "INSERT INTO toques (fecha, hora_inicio, hora_fin) VALUES (%s, %s, %s) RETURNING id",
            (fecha, hora_inicio, hora_fin)
        )
        id_toque = cur.fetchone()[0]

        # Insert into solicitudes
        cur.execute(
            "INSERT INTO solicitudes (id_artista, id_venue, id_toque, estado, timestamp) VALUES (%s, %s, %s, %s, NOW())",
            (id_artista, venue_id, id_toque, "pendiente")
        )
        conn.commit()
        flash("Solicitud enviada exitosamente.")
        return redirect("/home")

    # Query the venue info from the database using venue_id
    cur.execute("SELECT nombre_venue, descripcion_venue, imagen_venue FROM venues WHERE id = %s", (venue_id,))
    venue = cur.fetchone()
    if not venue:
        return apology("Venue not found", 404)
    venue_name, venue_description, venue_image = venue
    return render_template("book.html", venue_name=venue_name, venue_description=venue_description, venue_image=venue_image)

@app.route("/manage", methods=["GET", "POST"])
@login_required
def manage():
    user_id = session.get("user_id")
    user_type = session.get("register_user_type")

    # Handle accept/reject actions for venues
    if request.method == "POST" and user_type == "venue":
        solicitud_id = request.form.get("solicitud_id")
        action = request.form.get("action")
        if solicitud_id and action in ["aceptar", "rechazar"]:
            new_status = "aceptado" if action == "aceptar" else "rechazado"
            cur.execute("UPDATE solicitudes SET estado = %s WHERE id = %s", (new_status, solicitud_id))
            conn.commit()

    if user_type == "artista":
        # Get artist id
        cur.execute("SELECT id FROM artists WHERE id_usuario = %s", (user_id,))
        artist_row = cur.fetchone()
        artist_id = artist_row[0] if artist_row else None

        # Get accepted bookings for artist
        cur.execute("""
            SELECT s.id, v.nombre_venue, v.direccion, t.fecha, t.hora_inicio, t.hora_fin, v.imagen_venue, u.telefono
            FROM solicitudes s
            JOIN venues v ON s.id_venue = v.id
            JOIN usuarios u ON v.id_usuario = u.id
            JOIN toques t ON s.id_toque = t.id
            WHERE s.id_artista = %s AND s.estado = 'aceptado'
            ORDER BY t.fecha, t.hora_inicio
        """, (artist_id,))
        bookings = cur.fetchall()
        cur.execute("SELECT telefono FROM usuarios a JOIN artists b ON a.id = b.id_usuario JOIN venues c ON a.id = c.id_usuario WHERE a.id = %s", (user_id,))
        telefono = cur.fetchall()
        return render_template("manage.html", user_type=user_type, bookings=bookings, telefono=telefono)

    else:  # venue
        # Get venue id
        cur.execute("SELECT id FROM venues WHERE id_usuario = %s", (user_id,))
        venue_row = cur.fetchone()
        venue_id = venue_row[0] if venue_row else None

        # Get accepted bookings for venue
        cur.execute("""
            SELECT s.id, a.nombre_artista, a.descripcion_artista, t.fecha, t.hora_inicio, t.hora_fin, a.imagen_artista, u.telefono
            FROM solicitudes s
            JOIN artists a ON s.id_artista = a.id
            JOIN usuarios u ON a.id_usuario = u.id
            JOIN toques t ON s.id_toque = t.id
            WHERE s.id_venue = %s AND s.estado = 'aceptado'
            ORDER BY t.fecha, t.hora_inicio
        """, (venue_id,))
        bookings = cur.fetchall()

        # Get pending requests for venue
        cur.execute("""
            SELECT s.id, a.nombre_artista, a.descripcion_artista, t.fecha, t.hora_inicio, t.hora_fin, a.imagen_artista
            FROM solicitudes s
            JOIN artists a ON s.id_artista = a.id
            JOIN toques t ON s.id_toque = t.id
            WHERE s.id_venue = %s AND s.estado = 'pendiente'
            ORDER BY t.fecha, t.hora_inicio
        """, (venue_id,))
        requests = cur.fetchall()
        cur.execute("SELECT telefono FROM usuarios a JOIN artists b ON a.id = b.id_usuario JOIN venues c ON a.id = c.id_usuario WHERE a.id = %s", (user_id,))
        telefono = cur.fetchall()
        return render_template("manage.html", user_type=user_type, bookings=bookings, requests=requests, telefono=telefono)

