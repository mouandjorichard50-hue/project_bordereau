from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'cle_secrete_scolarite_2025_finale'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'ecole_v3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# MODÈLES DE DONNÉES
# ==========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    matricule = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    notes = db.relationship('Note', backref='etudiant', lazy=True)

class Matiere(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_matiere = db.Column(db.String(100), nullable=False)
    nom_professeur = db.Column(db.String(100))
    coefficient = db.Column(db.Integer, default=1)
    notes = db.relationship('Note', backref='matiere', lazy=True)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_obtenue = db.Column(db.Float, nullable=False)
    session = db.Column(db.String(50))
    requete_erreur = db.Column(db.Text, nullable=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow) 
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    matiere_id = db.Column(db.Integer, db.ForeignKey('matiere.id'), nullable=False)

# ==========================================
# SÉCURITÉ
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Accès réservé à l'administration.", "danger")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# ROUTES ÉTUDIANTS
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(matricule=request.form.get('matricule'), is_admin=False).first()
        if user and user.password_hash == request.form.get('password'):
            session['user_id'] = user.id
            session['is_admin'] = False
            return redirect(url_for('dashboard'))
        flash("Identifiants incorrects.", "danger")
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    notes = Note.query.filter_by(user_id=user.id).all()
    
    total_points = 0
    total_coefs = 0
    for n in notes:
        total_points += (n.note_obtenue * n.matiere.coefficient)
        total_coefs += n.matiere.coefficient
    
    moyenne = total_points / total_coefs if total_coefs > 0 else 0
    return render_template('dashboard.html', notes=notes, moyenne=moyenne, user=user)

@app.route('/requete/<int:note_id>', methods=['GET', 'POST'])
@login_required
def formulaire_requete(note_id):
    note = Note.query.get_or_404(note_id)
    if request.method == 'POST':
        note.requete_erreur = request.form.get('requete_text')
        note.date_creation = datetime.utcnow()
        db.session.commit()
        flash("Votre réclamation a été transmise.", "success")
        return redirect(url_for('dashboard'))
    return render_template('formulaire_requete.html', note=note)

# ==========================================
# ROUTES ADMINISTRATION
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = User.query.filter_by(matricule=request.form.get('matricule'), is_admin=True).first()
        if user and user.password_hash == request.form.get('password'):
            session['user_id'] = user.id
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash("Identifiants admin incorrects.", "danger")
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    requetes = Note.query.filter(Note.requete_erreur != None).order_by(Note.date_creation.desc()).all()
    # Tri alphabétique pour la liste principale
    etudiants = User.query.filter_by(is_admin=False).order_by(User.nom.asc()).all()
    return render_template('admin_dashboard.html', notes_avec_requetes=requetes, etudiants=etudiants)

@app.route('/admin/ajouter_etudiant', methods=['POST'])
@admin_required
def ajouter_etudiant():
    nom = request.form.get('nom')
    password = request.form.get('password')
    count = User.query.filter_by(is_admin=False).count()
    new_matricule = f"24G{count + 1:03d}"
    if nom and password:
        new_user = User(nom=nom, matricule=new_matricule, password_hash=password, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        flash(f"Étudiant {nom} ajouté ! Matricule : {new_matricule}", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/modifier_etudiant/<int:id>', methods=['GET', 'POST'])
@admin_required
def modifier_etudiant(id):
    etu = User.query.get_or_404(id)
    if request.method == 'POST':
        etu.nom = request.form.get('nom')
        etu.password_hash = request.form.get('password')
        db.session.commit()
        flash(f"Informations de {etu.nom} mises à jour.", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_modifier_etudiant.html', etu=etu)

@app.route('/admin/supprimer_etudiant/<int:id>')
@admin_required
def supprimer_etudiant(id):
    etu = User.query.get_or_404(id)
    # On supprime d'abord ses notes pour éviter les erreurs de lien
    Note.query.filter_by(user_id=id).delete()
    db.session.delete(etu)
    db.session.commit()
    flash("Étudiant et ses notes supprimés.", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/matiere', methods=['GET', 'POST'])
@admin_required
def gestion_matiere():
    if request.method == 'POST':
        m = Matiere(
            nom_matiere=request.form.get('nom_matiere'),
            nom_professeur=request.form.get('nom_professeur'),
            coefficient=int(request.form.get('coefficient'))
        )
        db.session.add(m)
        db.session.commit()
        flash("Matière créée.", "success")
    matieres = Matiere.query.all()
    return render_template('admin_matiere.html', matieres=matieres)

@app.route('/admin/note', methods=['GET', 'POST'])
@admin_required
def saisie_note():
    matieres = Matiere.query.all()
    etudiants = User.query.filter_by(is_admin=False).order_by(User.nom.asc()).all()
    if request.method == 'POST':
        matiere_id = request.form.get('matiere_id')
        session_type = request.form.get('session_type')
        for etu in etudiants:
            note_val = request.form.get(f'note_{etu.id}')
            if note_val and note_val.strip() != "":
                note = Note.query.filter_by(user_id=etu.id, matiere_id=matiere_id, session=session_type).first()
                if note:
                    note.note_obtenue = float(note_val)
                    note.requete_erreur = None
                    note.date_creation = datetime.utcnow()
                else:
                    nouvelle_note = Note(user_id=etu.id, matiere_id=matiere_id, session=session_type, note_obtenue=float(note_val))
                    db.session.add(nouvelle_note)
        db.session.commit()
        flash(f"Notes enregistrées avec succès.", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_note.html', etudiants=etudiants, matieres=matieres)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(matricule='ADM01').first():
            adm = User(nom="Direction", matricule="ADM01", password_hash="admin123", is_admin=True)
            db.session.add(adm)
            db.session.commit()
    app.run(debug=True)