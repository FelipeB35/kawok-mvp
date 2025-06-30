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
    session.clear()
    if request.method == "POST":
        user = request.form.get("username")
        password = request.form.get("password")
        if not user:
            return apology("Debes proveer un usuario", 400)
        if not password:
            return apology("Debes proveer una contraseña", 400)

        result = supabase.table("usuarios").select("*").eq("usuario", user).execute()
        rows = result.data

        if len(rows) != 1 or not check_password_hash(rows[0]["contraseña"], password):
            return apology("Contraseña o usuario inválidos.", 400)

        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["usuario"]

        artist_check = supabase.table("artists").select("id").eq("id_usuario", session["user_id"]).execute()
        if artist_check.data:
            session["register_user_type"] = "artista"
        else:
            session["register_user_type"] = "venue"
        return redirect("/home")
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
    session["register_user_type"] = request.form.get("user_type")
    user_type = session.get("register_user_type", "artista")
    if request.method == "POST":
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

        exists = supabase.table("usuarios").select("*").or_(
            f"usuario.eq.{request.form.get('usuario')},correo.eq.{request.form.get('correo')}"
        ).execute()
        if exists.data:
            return apology("El nombre de usuario o el correo electrónico ya existen", 400)
        if request.form.get("contraseña") != request.form.get("confirmar"):
            return apology("Las contraseñas deben coincidir", 400)
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
    ciudades = supabase.table("ciudades").select("*").execute().data
    generos = supabase.table("generos").select("*").execute().data
    if request.method == "POST":
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
        else:
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
    user_type = session.get("register_user_type", "artista")
    if request.method == "POST":
        if not request.form.get("fee_range"):
            return apology("Debes proporcionar un rango de fee", 400)
        if not request.form.get("descripcion"):
            return apology("Debes proporcionar una descripción", 400)
        if "image_upload" not in request.files or request.files["image_upload"].filename == "":
            return apology("Debes proporcionar una foto", 400)
        image = request.files["image_upload"]
        if image and image.filename != "":
            ext = os.path.splitext(secure_filename(image.filename))[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            if user_type == "artista":
                storage_path = f"artistas/{unique_name}"
            else:
                storage_path = f"venues/{unique_name}"
            public_url = upload_to_supabase_storage(image, storage_path)
            image_db_path = public_url
        else:
            image_db_path = None
        if user_type == "artista":
            session["register_step3"] = {
                "fee_range": request.form.get("fee_range"),
                "descripcion": request.form.get("descripcion"),
                "image_upload": image_db_path,
            }
        else:
            session["register_step3"] = {
                "fee_range": request.form.get("fee_range"),
                "descripcion": request.form.get("descripcion"),
                "image_upload": image_db_path,
            }
        # Insert user into usuarios
        user_insert = supabase.table("usuarios").insert({
            "nombre": session["register_step1"]["nombre"],
            "usuario": session["register_step1"]["usuario"],
            "contraseña": generate_password_hash(session["register_step1"]["contraseña"]),
            "correo": session["register_step1"]["correo"],
            "telefono": session["register_step2"]["telefono"],
            "id_ciudad": session["register_step2"]["ciudad"]
        }).execute()
        user_id = user_insert.data[0]["id"]
        if user_type == "artista":
            supabase.table("artists").insert({
                "nombre_artista": session["register_step2"]["nombre_artista"],
                "id_usuario": user_id,
                "id_genero": session["register_step2"]["genero"],
                "fee_max": session["register_step3"]["fee_range"],
                "descripcion_artista": session["register_step3"]["descripcion"],
                "imagen_artista": session["register_step3"]["image_upload"],
                "dui": session["register_step2"]["dui"]
            }).execute()
        else:
            supabase.table("venues").insert({
                "nombre_venue": session["register_step2"]["nombre_venue"],
                "nit": session["register_step2"]["nit"],
                "direccion": session["register_step2"]["direccion"],
                "pago_max": session["register_step3"]["fee_range"],
                "id_usuario": user_id,
                "descripcion_venue": session["register_step3"]["descripcion"],
                "imagen_venue": session["register_step3"]["image_upload"]
            }).execute()
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
        cards = supabase.table("venues").select("nombre_venue, imagen_venue").execute().data
        artist_row = supabase.table("artists").select("id").eq("id_usuario", user_id).execute().data
        artist_id = artist_row[0]["id"] if artist_row else None
        bookings = supabase.table("solicitudes") \
            .select("id, venues(nombre_venue, direccion, imagen_venue, usuarios(telefono)), toques(fecha, hora_inicio, hora_fin)") \
            .eq("id_artista", artist_id).eq("estado", "aceptado") \
            .order("toques.fecha").order("toques.hora_inicio").execute().data
    else:
        cards = supabase.table("artists").select("nombre_artista, imagen_artista").execute().data
        venue_row = supabase.table("venues").select("id").eq("id_usuario", user_id).execute().data
        venue_id = venue_row[0]["id"] if venue_row else None
        bookings = supabase.table("solicitudes") \
            .select("id, artists(nombre_artista, descripcion_artista, imagen_artista, usuarios(telefono)), toques(fecha, hora_inicio, hora_fin)") \
            .eq("id_venue", venue_id).eq("estado", "aceptado") \
            .order("toques.fecha").order("toques.hora_inicio").execute().data
    return render_template("home.html", user_type=user_type, cards=cards, bookings=bookings)

@app.route("/discover")
@login_required
def discover():
    user_type = session.get("register_user_type", "artista")
    search = request.args.get("q", "").strip()
    if user_type == "artista":
        if search:
            cards = supabase.table("venues").select("*").ilike("nombre_venue", f"%{search}%").execute().data
        else:
            cards = supabase.table("venues").select("*").execute().data
    else:
        if search:
            cards = supabase.table("artists").select("*").ilike("nombre_artista", f"%{search}%").execute().data
        else:
            cards = supabase.table("artists").select("*").execute().data
    return render_template("discover.html", user_type=user_type, cards=cards)

@app.route("/book/<int:venue_id>", methods=["GET", "POST"])
@login_required
def book(venue_id):
    if request.method == "POST":
        user_id = session.get("user_id")
        if not user_id:
            return apology("You must be logged in to book a venue", 403)
        artist_row = supabase.table("artists").select("id").eq("id_usuario", user_id).execute().data
        if not artist_row:
            return apology("No artist profile found.", 400)
        id_artista = artist_row[0]["id"]
        fecha_hora = request.form.get("fecha")
        if not fecha_hora:
            return apology("Debes seleccionar una fecha y hora", 400)
        from datetime import datetime, timedelta
        dt = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M")
        fecha = dt.date().isoformat()
        hora_inicio = dt.time().strftime("%H:%M:%S")
        hora_fin = (dt + timedelta(hours=1)).time().strftime("%H:%M:%S")
        toques_insert = supabase.table("toques").insert({
            "fecha": fecha,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin
        }).execute()
        id_toque = toques_insert.data[0]["id"]
        supabase.table("solicitudes").insert({
            "id_artista": id_artista,
            "id_venue": venue_id,
            "id_toque": id_toque,
            "estado": "pendiente"
        }).execute()
        flash("Solicitud enviada exitosamente.")
        return redirect("/home")
    venue = supabase.table("venues").select("nombre_venue, descripcion_venue, imagen_venue").eq("id", venue_id).execute().data
    if not venue:
        return apology("Venue not found", 404)
    venue_name = venue[0]["nombre_venue"]
    venue_description = venue[0]["descripcion_venue"]
    venue_image = venue[0]["imagen_venue"]
    return render_template("book.html", venue_name=venue_name, venue_description=venue_description, venue_image=venue_image)

@app.route("/manage", methods=["GET", "POST"])
@login_required
def manage():
    user_id = session.get("user_id")
    user_type = session.get("register_user_type")
    if request.method == "POST" and user_type == "venue":
        solicitud_id = request.form.get("solicitud_id")
        action = request.form.get("action")
        if solicitud_id and action in ["aceptar", "rechazar"]:
            new_status = "aceptado" if action == "aceptar" else "rechazado"
            supabase.table("solicitudes").update({"estado": new_status}).eq("id", solicitud_id).execute()
    if user_type == "artista":
        artist_row = supabase.table("artists").select("id").eq("id_usuario", user_id).execute().data
        artist_id = artist_row[0]["id"] if artist_row else None
        bookings = supabase.table("solicitudes") \
            .select("id, venues(nombre_venue, direccion, imagen_venue, usuarios(telefono)), toques(fecha, hora_inicio, hora_fin)") \
            .eq("id_artista", artist_id).eq("estado", "aceptado") \
            .order("toques.fecha").order("toques.hora_inicio").execute().data
        return render_template("manage.html", user_type=user_type, bookings=bookings)
    else:
        venue_row = supabase.table("venues").select("id").eq("id_usuario", user_id).execute().data
        venue_id = venue_row[0]["id"] if venue_row else None
        bookings = supabase.table("solicitudes") \
            .select("id, artists(nombre_artista, descripcion_artista, imagen_artista, usuarios(telefono)), toques(fecha, hora_inicio, hora_fin)") \
            .eq("id_venue", venue_id).eq("estado", "aceptado") \
            .order("toques.fecha").order("toques.hora_inicio").execute().data
        requests = supabase.table("solicitudes") \
            .select("id, artists(nombre_artista, descripcion_artista, imagen_artista, usuarios(telefono)), toques(fecha, hora_inicio, hora_fin)") \
            .eq("id_venue", venue_id).eq("estado", "pendiente") \
            .order("toques.fecha").order("toques.hora_inicio").execute().data
        return render_template("manage.html", user_type=user_type, bookings=bookings, requests=requests)

