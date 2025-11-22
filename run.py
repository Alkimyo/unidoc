from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# Flask ilovasini sozlash
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///unidoc.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Database va Login Manager
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Iltimos, avval tizimga kiring'
login_manager.login_message_category = 'warning'


# ==================== MODELS ====================

class User(UserMixin, db.Model):
    """Foydalanuvchi modeli"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student', index=True)
    department = db.Column(db.String(100))
    faculty = db.Column(db.String(100))
    student_id = db.Column(db.String(20), unique=True, index=True)
    guruh = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    documents = db.relationship('Document', foreign_keys='Document.author_id', 
                              backref='author', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', 
                                   lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Parolni hash qilish"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Parolni tekshirish"""
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        """To'liq ismni qaytarish"""
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<User {self.username}>'


class Document(db.Model):
    """Hujjat modeli"""
    __tablename__ = 'document'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    document_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), default='draft', index=True)
    
    # Foreign Keys
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    department_head_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    dean_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    supervisor = db.relationship('User', foreign_keys=[supervisor_id])
    department_head = db.relationship('User', foreign_keys=[department_head_id])
    dean = db.relationship('User', foreign_keys=[dean_id])
    approvals = db.relationship('DocumentApproval', backref='document', 
                               lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Document {self.title}>'


class DocumentApproval(db.Model):
    """Hujjat tasdiqlash modeli"""
    __tablename__ = 'document_approval'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False, index=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    approval_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approver = db.relationship('User', backref='approval_records')
    
    def __repr__(self):
        return f'<DocumentApproval {self.id}>'


class Notification(db.Model):
    """Bildirishnoma modeli"""
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<Notification {self.title}>'


# ==================== LOGIN MANAGER ====================

@login_manager.user_loader
def load_user(user_id):
    """Foydalanuvchini yuklash"""
    return User.query.get(int(user_id))


# ==================== HELPER FUNCTIONS ====================

def get_my_students():
    """O'qituvchining talabalarini qaytarish"""
    if not current_user.is_authenticated or current_user.role != 'teacher':
        return []
    return User.query.filter_by(
        role='student', 
        department=current_user.department,
        is_active=True
    ).order_by(User.last_name).all()


def get_department_users():
    """Kafedradagi foydalanuvchilarni qaytarish"""
    if not current_user.is_authenticated or current_user.role != 'department_head':
        return []
    return User.query.filter_by(
        department=current_user.department,
        is_active=True
    ).order_by(User.last_name).all()


def get_faculty_users():
    """Fakultetdagi foydalanuvchilarni qaytarish"""
    if not current_user.is_authenticated or current_user.role != 'dean':
        return []
    return User.query.filter_by(
        faculty=current_user.faculty,
        is_active=True
    ).order_by(User.last_name).all()


def get_all_users():
    """Barcha foydalanuvchilarni qaytarish"""
    if not current_user.is_authenticated or current_user.role != 'admin':
        return []
    return User.query.order_by(User.last_name).all()


def get_available_supervisors():
    """Ilmiy rahbarlarni qaytarish"""
    return User.query.filter_by(role='teacher', is_active=True).order_by(User.last_name).all()


def get_teachers():
    """O'qituvchilarni qaytarish"""
    return User.query.filter_by(role='teacher', is_active=True).order_by(User.last_name).all()


def get_department_heads():
    """Kafedra mudirlarini qaytarish"""
    return User.query.filter_by(role='department_head', is_active=True).order_by(User.last_name).all()


def get_deans():
    """Dekanlarni qaytarish"""
    return User.query.filter_by(role='dean', is_active=True).order_by(User.last_name).all()


def get_allowed_document_types(user_role):
    """Ruxsat etilgan hujjat turlarini qaytarish"""
    document_types = {
        'student': {
            'diploma_project': 'Diplom loyihasi',
            'course_work': 'Kurs ishi',
            'thesis': 'Magistrlik dissertatsiyasi',
            'scientific_article': 'Ilmiy maqola',
            'application': 'Ariza',
            'other': 'Boshqa'
        },
        'teacher': {
            'diploma_project': 'Diplom loyihasi',
            'course_work': 'Kurs ishi',
            'thesis': 'Magistrlik dissertatsiyasi',
            'scientific_article': 'Ilmiy maqola',
            'methodological_guide': 'Metodik qo\'llanma',
            'syllabus': 'O\'quv dasturi',
            'test_assignment': 'Test topshirig\'i',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        },
        'department_head': {
            'department_report': 'Kafedra hisoboti',
            'work_plan': 'Ish rejasi',
            'protocol': 'Protokol',
            'order': 'Buyruq',
            'scientific_article': 'Ilmiy maqola',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        },
        'dean': {
            'faculty_report': 'Fakultet hisoboti',
            'order': 'Buyruq',
            'protocol': 'Protokol',
            'work_plan': 'Ish rejasi',
            'academic_plan': 'O\'quv reja',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        },
        'admin': {
            'diploma_project': 'Diplom loyihasi',
            'course_work': 'Kurs ishi',
            'thesis': 'Magistrlik dissertatsiyasi',
            'scientific_article': 'Ilmiy maqola',
            'methodological_guide': 'Metodik qo\'llanma',
            'department_report': 'Kafedra hisoboti',
            'faculty_report': 'Fakultet hisoboti',
            'work_plan': 'Ish rejasi',
            'protocol': 'Protokol',
            'order': 'Buyruq',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        }
    }
    return document_types.get(user_role, {})


def can_create_document_for_user(creator, target_user):
    """Hujjat yaratish huquqini tekshirish"""
    if creator.role == 'admin':
        return True
    elif creator.role == 'dean':
        return target_user.faculty == creator.faculty
    elif creator.role == 'department_head':
        return target_user.department == creator.department
    elif creator.role == 'teacher':
        return (target_user.role == 'student' and 
                target_user.department == creator.department)
    else:
        return creator.id == target_user.id


def create_notification(user_id, title, message):
    """Bildirishnoma yaratish"""
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Notification error: {str(e)}")
        db.session.rollback()
        return False


# ==================== CONTEXT PROCESSOR ====================

@app.context_processor
def utility_processor():
    """Template'lar uchun yordamchi funksiyalar"""
    return dict(
        get_my_students=get_my_students,
        get_department_users=get_department_users,
        get_faculty_users=get_faculty_users,
        get_all_users=get_all_users,
        get_available_supervisors=get_available_supervisors,
        get_teachers=get_teachers,
        get_department_heads=get_department_heads,
        get_deans=get_deans,
        get_allowed_document_types=get_allowed_document_types
    )


# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    """Asosiy sahifa"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login sahifasi"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                flash('Username va parol kiritilishi shart!', 'danger')
                return render_template('login.html')
            
            # Foydalanuvchini topish
            user = User.query.filter_by(username=username).first()
            
            if not user:
                flash('Login yoki parol noto\'g\'ri!', 'danger')
                return render_template('login.html')
            
            if not user.check_password(password):
                flash('Login yoki parol noto\'g\'ri!', 'danger')
                return render_template('login.html')
            
            if not user.is_active:
                flash('Hisobingiz hali faollashtirilmagan. Administrator bilan bog\'laning.', 'warning')
                return render_template('login.html')
            
            # Login
            login_user(user, remember=request.form.get('remember', False))
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Redirect
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                flash(f'Xush kelibsiz, {user.get_full_name()}!', 'success')
                return redirect(next_page)
            
            flash(f'Xush kelibsiz, {user.get_full_name()}!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('Tizimda xatolik yuz berdi. Qaytadan urinib ko\'ring.', 'danger')
            db.session.rollback()
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('Siz tizimdan chiqdingiz', 'info')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Ro'yxatdan o'tish"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            # Form ma'lumotlarini olish
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            department = request.form.get('department', '').strip()
            faculty = request.form.get('faculty', '').strip()
            student_id = request.form.get('student_id', '').strip()
            guruh = request.form.get('guruh', '').strip()
            
            # Validatsiya
            errors = []
            
            if not all([username, email, password, first_name, last_name, department, faculty, student_id, guruh]):
                errors.append('Barcha maydonlar to\'ldirilishi shart!')
            
            if User.query.filter_by(username=username).first():
                errors.append('Bu foydalanuvchi nomi band!')
            
            if User.query.filter_by(email=email).first():
                errors.append('Bu email manzili band!')
            
            if User.query.filter_by(student_id=student_id).first():
                errors.append('Bu Talaba ID band!')
            
            if password != confirm_password:
                errors.append('Parollar mos kelmadi!')
            
            if len(password) < 6:
                errors.append('Parol kamida 6 belgidan iborat bo\'lishi kerak!')
            
            if errors:
                for error in errors:
                    flash(error, 'danger')
                return render_template('register.html')
            
            # Yangi foydalanuvchi yaratish
            new_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='student',
                department=department,
                faculty=faculty,
                student_id=student_id,
                guruh=guruh,
                is_active=False
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            # Adminlarga bildirishnoma yuborish
            admins = User.query.filter_by(role='admin', is_active=True).all()
            for admin in admins:
                create_notification(
                    admin.id,
                    "Yangi talaba ro'yxatdan o'tdi",
                    f"{first_name} {last_name} ({student_id}) tizimda ro'yxatdan o'tdi."
                )
            
            flash('Ro\'yxatdan muvaffaqiyatli o\'tdingiz! Administrator tasdiqlashini kuting.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"Register error: {str(e)}")
            flash('Xatolik yuz berdi. Qaytadan urinib ko\'ring.', 'danger')
            db.session.rollback()
    
    return render_template('register.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard sahifasi"""
    try:
        user_docs = Document.query.filter_by(author_id=current_user.id).count()
        pending_approvals = 0
        
        if current_user.role in ['teacher', 'department_head', 'dean']:
            pending_approvals = DocumentApproval.query.filter_by(
                approver_id=current_user.id,
                status='pending'
            ).count()
        
        recent_docs = Document.query.filter_by(author_id=current_user.id).order_by(
            Document.created_at.desc()
        ).limit(5).all()
        
        unread_notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
        
        return render_template('dashboard.html',
                             user_docs=user_docs,
                             pending_approvals=pending_approvals,
                             recent_docs=recent_docs,
                             unread_notifications=unread_notifications)
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        flash('Dashboard yuklanishda xatolik', 'danger')
        return render_template('dashboard.html',
                             user_docs=0,
                             pending_approvals=0,
                             recent_docs=[],
                             unread_notifications=0)


@app.route('/documents')
@login_required
def documents():
    """Hujjatlar sahifasi"""
    try:
        user_docs = Document.query.filter_by(author_id=current_user.id).order_by(
            Document.created_at.desc()
        ).all()
        return render_template('documents.html', documents=user_docs)
    except Exception as e:
        print(f"Documents error: {str(e)}")
        flash('Hujjatlar yuklanishda xatolik', 'danger')
        return render_template('documents.html', documents=[])


@app.route('/create-document', methods=['GET', 'POST'])
@login_required
def create_document():
    """Hujjat yaratish"""
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            document_type = request.form.get('document_type', '')
            
            if not title or not document_type:
                flash('Sarlavha va hujjat turi kiritilishi shart!', 'danger')
                return render_template('create_document.html')
            
            # Hujjat turini tekshirish
            allowed_types = get_allowed_document_types(current_user.role)
            if document_type not in allowed_types:
                flash('Siz ushbu turdagi hujjat yarata olmaysiz!', 'danger')
                return render_template('create_document.html')
            
            # Muallifni aniqlash
            if current_user.role in ['admin', 'teacher', 'department_head', 'dean']:
                author_id = request.form.get('author_id', current_user.id)
            else:
                author_id = current_user.id
            
            author = User.query.get(author_id)
            if not author:
                flash('Muallif topilmadi!', 'danger')
                return render_template('create_document.html')
            
            if not can_create_document_for_user(current_user, author):
                flash('Siz bu foydalanuvchi uchun hujjat yarata olmaysiz!', 'danger')
                return render_template('create_document.html')
            
            # Yangi hujjat yaratish
            new_doc = Document(
                title=title,
                description=description,
                document_type=document_type,
                author_id=author_id,
                status='draft'
            )
            
            # Tasdiqlovchilarni qo'shish
            supervisor_id = request.form.get('supervisor_id')
            if supervisor_id:
                new_doc.supervisor_id = supervisor_id
            
            department_head_id = request.form.get('department_head_id')
            if department_head_id:
                new_doc.department_head_id = department_head_id
            
            dean_id = request.form.get('dean_id')
            if dean_id:
                new_doc.dean_id = dean_id
            
            db.session.add(new_doc)
            db.session.commit()
            
            flash('Hujjat muvaffaqiyatli yaratildi!', 'success')
            return redirect(url_for('documents'))
            
        except Exception as e:
            print(f"Create document error: {str(e)}")
            flash('Hujjat yaratishda xatolik!', 'danger')
            db.session.rollback()
    
    return render_template('create_document.html')


@app.route('/profile')
@login_required
def profile():
    """Profil sahifasi"""
    return render_template('profile.html')


@app.route('/settings')
@login_required
def settings():
    """Sozlamalar sahifasi"""
    return render_template('settings.html')


# ==================== API ENDPOINTS ====================

@app.route('/api/notifications')
@login_required
def get_notifications():
    """Bildirishnomalarni olish"""
    try:
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(Notification.created_at.desc()).limit(10).all()
        
        notifications_data = [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
        } for n in notifications]
        
        return jsonify({
            'success': True,
            'count': len(notifications),
            'notifications': notifications_data
        })
    except Exception as e:
        print(f"Get notifications error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/document/<int:doc_id>/submit', methods=['POST'])
@login_required
def submit_document(doc_id):
    """Hujjatni yuborish"""
    try:
        document = Document.query.get_or_404(doc_id)
        
        if document.author_id != current_user.id:
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
        
        if document.status != 'draft':
            return jsonify({'success': False, 'error': 'Faqat qoralama hujjatlarni yuborish mumkin'}), 400
        
        document.status = 'submitted'
        document.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Supervisor ga bildirishnoma
        if document.supervisor_id:
            create_notification(
                document.supervisor_id,
                "Yangi hujjat tasdiq kutmoqda",
                f"{current_user.get_full_name()} '{document.title}' hujjatini yubordi."
            )
        
        return jsonify({'success': True, 'message': 'Hujjat muvaffaqiyatli yuborildi!'})
    except Exception as e:
        print(f"Submit document error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/document/<int:doc_id>/approve', methods=['POST'])
@login_required
def approve_document(doc_id):
    """Hujjatni tasdiqlash"""
    try:
        document = Document.query.get_or_404(doc_id)
        data = request.get_json() or {}
        comments = data.get('comments', '')
        
        # Huquqni tekshirish
        can_approve = False
        next_status = None
        approval_type = None
        
        if current_user.role == 'teacher' and document.supervisor_id == current_user.id:
            if document.status == 'submitted':
                can_approve = True
                next_status = 'supervisor_approved'
                approval_type = 'supervisor'
        elif current_user.role == 'department_head' and document.department_head_id == current_user.id:
            if document.status == 'supervisor_approved':
                can_approve = True
                next_status = 'department_approved'
                approval_type = 'department_head'
        elif current_user.role == 'dean' and document.dean_id == current_user.id:
            if document.status == 'department_approved':
                can_approve = True
                next_status = 'approved'
                approval_type = 'dean'
        
        if not can_approve:
            return jsonify({'success': False, 'error': 'Tasdiqlash huquqi yo\'q'}), 403
        
        # Tasdiqlash
        approval = DocumentApproval(
            document_id=doc_id,
            approver_id=current_user.id,
            approval_type=approval_type,
            status='approved',
            comments=comments
        )
        
        document.status = next_status
        document.updated_at = datetime.utcnow()
        
        db.session.add(approval)
        db.session.commit()
        
        # Muallifga bildirishnoma
        create_notification(
            document.author_id,
            "Hujjat tasdiqlandi",
            f"Sizning '{document.title}' hujjatingiz {current_user.get_full_name()} tomonidan tasdiqlandi."
        )
        
        return jsonify({'success': True, 'message': 'Hujjat tasdiqlandi!'})
    except Exception as e:
        print(f"Approve document error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    """404 xato"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500 xato"""
    db.session.rollback()
    return render_template('500.html'), 500


@app.errorhandler(403)
def forbidden_error(error):
    """403 xato"""
    return render_template('403.html'), 403


# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@login_required
def admin():
    """Admin panel"""
    if current_user.role != 'admin':
        flash('Admin paneliga kirish huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        users_count = User.query.count()
        documents_count = Document.query.count()
        pending_approvals = DocumentApproval.query.filter_by(status='pending').count()
        inactive_users = User.query.filter_by(is_active=False).count()
        
        return render_template('admin_dashboard.html',
                             users_count=users_count,
                             documents_count=documents_count,
                             pending_approvals=pending_approvals,
                             inactive_users=inactive_users)
    except Exception as e:
        print(f"Admin dashboard error: {str(e)}")
        flash('Admin panel yuklanishda xatolik', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/admin/users')
@login_required
def admin_users():
    """Foydalanuvchilarni boshqarish"""
    if current_user.role != 'admin':
        flash('Ruxsat yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('admin_users.html', users=users)
    except Exception as e:
        print(f"Admin users error: {str(e)}")
        flash('Xatolik yuz berdi', 'danger')
        return redirect(url_for('admin'))


@app.route('/admin/users/add', methods=['POST'])
@login_required
def admin_add_user():
    """Yangi foydalanuvchi qo'shish"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
    
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', '')
        department = request.form.get('department', '').strip()
        faculty = request.form.get('faculty', '').strip()
        student_id = request.form.get('student_id', '').strip() if role == 'student' else None
        guruh = request.form.get('guruh', '').strip() if role == 'student' else None
        
        # Validatsiya
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username band!'})
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email band!'})
        
        if role == 'student' and student_id and User.query.filter_by(student_id=student_id).first():
            return jsonify({'success': False, 'error': 'Talaba ID band!'})
        
        # Yangi foydalanuvchi
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            department=department,
            faculty=faculty,
            student_id=student_id,
            guruh=guruh,
            is_active=True
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Foydalanuvchi qo\'shildi!'})
    except Exception as e:
        print(f"Add user error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
@login_required
def admin_activate_user(user_id):
    """Foydalanuvchini faollashtirish"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        user.is_active = True
        db.session.commit()
        
        # Bildirishnoma
        create_notification(
            user_id,
            "Hisobingiz faollashtirildi",
            "Administrator hisobingizni faollashtirdi. Tizimga kirishingiz mumkin."
        )
        
        return jsonify({'success': True, 'message': 'Faollashtirildi!'})
    except Exception as e:
        print(f"Activate user error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
def admin_deactivate_user(user_id):
    """Foydalanuvchini o'chirish"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'O\'zingizni o\'chira olmaysiz!'}), 400
        
        user.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Foydalanuvchi o\'chirildi!'})
    except Exception as e:
        print(f"Deactivate user error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    """Foydalanuvchini butunlay o'chirish"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'O\'zingizni o\'chira olmaysiz!'}), 400
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Foydalanuvchi o\'chirildi!'})
    except Exception as e:
        print(f"Delete user error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/users/<int:user_id>/update-role', methods=['POST'])
@login_required
def admin_update_user_role(user_id):
    """Foydalanuvchi rolini o'zgartirish"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json() or {}
        new_role = data.get('role', '')
        
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'O\'z rolingizni o\'zgartira olmaysiz!'}), 400
        
        valid_roles = ['student', 'teacher', 'department_head', 'dean', 'admin']
        if new_role not in valid_roles:
            return jsonify({'success': False, 'error': 'Noto\'g\'ri rol!'}), 400
        
        old_role = user.role
        user.role = new_role
        
        # Talaba bo'lmasa, student ma'lumotlarini o'chirish
        if old_role == 'student' and new_role != 'student':
            user.student_id = None
            user.guruh = None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Rol o\'zgartirildi!',
            'new_role': new_role
        })
    except Exception as e:
        print(f"Update role error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/documents')
@login_required
def admin_documents():
    """Barcha hujjatlar"""
    if current_user.role != 'admin':
        flash('Ruxsat yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        documents = Document.query.order_by(Document.created_at.desc()).all()
        return render_template('admin_documents.html', documents=documents)
    except Exception as e:
        print(f"Admin documents error: {str(e)}")
        flash('Xatolik yuz berdi', 'danger')
        return redirect(url_for('admin'))


# ==================== APPROVAL ROUTES ====================

@app.route('/approvals')
@login_required
def approvals():
    """Tasdiqlanishi kerak bo'lgan hujjatlar"""
    if current_user.role not in ['teacher', 'department_head', 'dean']:
        flash('Ruxsat yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        pending_docs = []
        
        if current_user.role == 'teacher':
            pending_docs = Document.query.filter_by(
                supervisor_id=current_user.id,
                status='submitted'
            ).order_by(Document.created_at.desc()).all()
        elif current_user.role == 'department_head':
            pending_docs = Document.query.filter_by(
                department_head_id=current_user.id,
                status='supervisor_approved'
            ).order_by(Document.created_at.desc()).all()
        elif current_user.role == 'dean':
            pending_docs = Document.query.filter_by(
                dean_id=current_user.id,
                status='department_approved'
            ).order_by(Document.created_at.desc()).all()
        
        return render_template('approvals.html', pending_docs=pending_docs)
    except Exception as e:
        print(f"Approvals error: {str(e)}")
        flash('Xatolik yuz berdi', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/my-submissions')
@login_required
def my_submissions():
    """Yuborilgan hujjatlarim"""
    try:
        submissions = Document.query.filter(
            Document.author_id == current_user.id,
            Document.status.in_(['submitted', 'supervisor_approved', 'department_approved', 'approved', 'rejected'])
        ).order_by(Document.updated_at.desc()).all()
        
        return render_template('my_submissions.html', submissions=submissions)
    except Exception as e:
        print(f"Submissions error: {str(e)}")
        flash('Xatolik yuz berdi', 'danger')
        return redirect(url_for('documents'))


@app.route('/document/<int:doc_id>/view')
@login_required
def view_document(doc_id):
    """Hujjatni ko'rish"""
    try:
        document = Document.query.get_or_404(doc_id)
        
        # Huquqni tekshirish
        can_view = (
            document.author_id == current_user.id or
            document.supervisor_id == current_user.id or
            document.department_head_id == current_user.id or
            document.dean_id == current_user.id or
            current_user.role == 'admin'
        )
        
        if not can_view:
            flash('Bu hujjatni ko\'rish huquqingiz yo\'q!', 'danger')
            return redirect(url_for('documents'))
        
        return render_template('view_document.html', document=document)
    except Exception as e:
        print(f"View document error: {str(e)}")
        flash('Hujjat topilmadi', 'danger')
        return redirect(url_for('documents'))


@app.route('/api/document/<int:doc_id>/progress')
@login_required
def document_progress(doc_id):
    """Hujjat jarayoni"""
    try:
        document = Document.query.get_or_404(doc_id)
        
        if document.author_id != current_user.id:
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
        
        # Status ma'lumotlari
        status_info = {
            'draft': {'text': 'Qoralama', 'class': 'warning'},
            'submitted': {'text': 'Yuborilgan', 'class': 'info'},
            'supervisor_approved': {'text': 'Rahbar tasdiqladi', 'class': 'primary'},
            'department_approved': {'text': 'Kafedra tasdiqladi', 'class': 'primary'},
            'approved': {'text': 'Tasdiqlangan', 'class': 'success'},
            'rejected': {'text': 'Rad etilgan', 'class': 'danger'}
        }
        
        current_status = status_info.get(document.status, {'text': document.status, 'class': 'secondary'})
        
        # Tasdiqlash tarixi
        approvals_data = []
        for approval in document.approvals.order_by(DocumentApproval.created_at).all():
            approvals_data.append({
                'approver_name': approval.approver.get_full_name(),
                'approval_type': approval.approval_type.replace('_', ' ').title(),
                'status': 'Tasdiqlangan' if approval.status == 'approved' else 'Rad etilgan',
                'status_class': 'success' if approval.status == 'approved' else 'danger',
                'comments': approval.comments or '',
                'date': approval.created_at.strftime('%d.%m.%Y %H:%M')
            })
        
        return jsonify({
            'success': True,
            'document': {
                'id': document.id,
                'title': document.title,
                'type': document.document_type.replace('_', ' ').title(),
                'status': document.status,
                'status_text': current_status['text'],
                'status_class': current_status['class'],
                'created_at': document.created_at.strftime('%d.%m.%Y'),
                'updated_at': document.updated_at.strftime('%d.%m.%Y %H:%M')
            },
            'approvals': approvals_data
        })
    except Exception as e:
        print(f"Document progress error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/document/<int:doc_id>/resubmit', methods=['POST'])
@login_required
def document_resubmit(doc_id):
    """Hujjatni qayta yuborish"""
    try:
        document = Document.query.get_or_404(doc_id)
        
        if document.author_id != current_user.id:
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
        
        if document.status != 'rejected':
            return jsonify({'success': False, 'error': 'Faqat rad etilgan hujjatlarni qayta yuborish mumkin'}), 400
        
        # Qayta yuborish
        document.status = 'submitted'
        document.updated_at = datetime.utcnow()
        
        # Eski tasdiqlarni o'chirish
        DocumentApproval.query.filter_by(document_id=doc_id).delete()
        
        db.session.commit()
        
        # Supervisor ga bildirishnoma
        if document.supervisor_id:
            create_notification(
                document.supervisor_id,
                "Hujjat qayta yuborildi",
                f"{current_user.get_full_name()} '{document.title}' hujjatini qayta yubordi."
            )
        
        return jsonify({'success': True, 'message': 'Hujjat qayta yuborildi!'})
    except Exception as e:
        print(f"Resubmit error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/document/<int:doc_id>/reject', methods=['POST'])
@login_required
def reject_document(doc_id):
    """Hujjatni rad etish"""
    try:
        document = Document.query.get_or_404(doc_id)
        data = request.get_json() or {}
        comments = data.get('comments', '')
        
        # Huquqni tekshirish
        can_reject = (
            (current_user.role == 'teacher' and document.supervisor_id == current_user.id) or
            (current_user.role == 'department_head' and document.department_head_id == current_user.id) or
            (current_user.role == 'dean' and document.dean_id == current_user.id)
        )
        
        if not can_reject:
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
        
        # Rad etish
        approval_type = 'supervisor' if current_user.role == 'teacher' else current_user.role
        
        approval = DocumentApproval(
            document_id=doc_id,
            approver_id=current_user.id,
            approval_type=approval_type,
            status='rejected',
            comments=comments
        )
        
        document.status = 'rejected'
        document.updated_at = datetime.utcnow()
        
        db.session.add(approval)
        db.session.commit()
        
        # Muallifga bildirishnoma
        create_notification(
            document.author_id,
            "Hujjat rad etildi",
            f"Sizning '{document.title}' hujjatingiz rad etildi. Sabab: {comments}"
        )
        
        return jsonify({'success': True, 'message': 'Hujjat rad etildi!'})
    except Exception as e:
        print(f"Reject error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== INITIALIZATION ====================

def init_database():
    """Database yaratish va test ma'lumotlar qo'shish"""
    with app.app_context():
        # Jadvallarni yaratish
        db.create_all()
        
        # Test foydalanuvchilar
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@unidoc.uz',
                first_name='Admin',
                last_name='Administrator',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        if not User.query.filter_by(username='teacher1').first():
            teacher = User(
                username='teacher1',
                email='teacher1@unidoc.uz',
                first_name='O\'qituvchi',
                last_name='Rahmatov',
                role='teacher',
                department='IT',
                faculty='Engineering',
                is_active=True
            )
            teacher.set_password('teacher123')
            db.session.add(teacher)
        
        if not User.query.filter_by(username='student1').first():
            student = User(
                username='student1',
                email='student1@unidoc.uz',
                first_name='Ali',
                last_name='Valiyev',
                role='student',
                department='IT',
                faculty='Engineering',
                student_id='202301001',
                guruh='IT-21',
                is_active=True
            )
            student.set_password('student123')
            db.session.add(student)
        
        try:
            db.session.commit()
            print("\n" + "="*50)
            print("DATABASE MUVAFFAQIYATLI YARATILDI!")
            print("="*50)
            print("\nTest foydalanuvchilar:")
            print("-" * 50)
            print("Admin:")
            print("  Username: admin")
            print("  Password: admin123")
            print("\nO'qituvchi:")
            print("  Username: teacher1")
            print("  Password: teacher123")
            print("\nTalaba:")
            print("  Username: student1")
            print("  Password: student123")
            print("="*50 + "\n")
        except Exception as e:
            print(f"Database yaratishda xatolik: {str(e)}")
            db.session.rollback()


# ==================== MAIN ====================

if __name__ == '__main__':
    init_database()
    print("Server ishga tushmoqda: http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
